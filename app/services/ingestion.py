from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

from app.core.settings import TraderConfig
from app.db.repository import Repository
from app.fyers.client import FyersLtpSocket, FyersRestClient
from app.services.pnl_engine import (
    compute_day_realized_from_trades,
    compute_realized_from_trades,
    compute_trader_totals,
)


logger = logging.getLogger(__name__)


@dataclass
class TraderRuntime:
    config: TraderConfig
    access_token: str
    rest_client: FyersRestClient
    positions: list[dict] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    pnl: dict[str, float] = field(
        default_factory=lambda: {
            "current_pnl": 0.0,
            "realized_pnl": 0.0,
            "day_realized_pnl": 0.0,
            "total_pnl": 0.0,
        }
    )
    ltp_cache: dict[str, float] = field(default_factory=dict)
    raw_positions_response: dict = field(default_factory=dict)
    raw_tradebook_response: dict = field(default_factory=dict)
    last_attempt_epoch: float = 0.0
    last_refresh_epoch: float = 0.0
    last_error: str = ""
    socket_symbols: set[str] = field(default_factory=set)
    socket: FyersLtpSocket | None = None


class IngestionService:
    def __init__(
        self,
        trader_tokens: list[tuple[TraderConfig, str]],
        repository: Repository,
        polling_interval_sec: float,
        websocket_enabled: bool,
        market_timezone: str,
    ) -> None:
        self.repository = repository
        self.polling_interval_sec = polling_interval_sec
        self.websocket_enabled = websocket_enabled
        self.market_timezone = market_timezone
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

        self._traders: dict[int, TraderRuntime] = {}
        for cfg, token in trader_tokens:
            rt = TraderRuntime(
                config=cfg,
                access_token=token,
                rest_client=FyersRestClient(client_id=cfg.client_id, access_token=token),
            )
            self._traders[cfg.id] = rt
            self.repository.upsert_trader(cfg.id, cfg.name, cfg.api_key, "***")

    def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._loop, name="ingestion-service", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

        for rt in self._traders.values():
            if rt.socket:
                rt.socket.close()

    def _loop(self) -> None:
        while self._running:
            started = time.time()
            for trader_id, rt in self._traders.items():
                try:
                    with self._lock:
                        rt.last_attempt_epoch = time.time()
                    self._refresh_trader(rt)
                except Exception as exc:
                    with self._lock:
                        rt.last_error = f"{type(exc).__name__}: {exc}"
                    logger.exception("Refresh failed for trader %s: %s", trader_id, exc)
            elapsed = time.time() - started
            sleep_for = max(0.5, self.polling_interval_sec - elapsed)
            time.sleep(sleep_for)

    def _refresh_trader(self, rt: TraderRuntime) -> None:
        raw_positions = self._with_retry(rt.rest_client.fetch_positions_raw)
        raw_tradebook = self._with_retry(rt.rest_client.fetch_tradebook_raw)

        with self._lock:
            rt.raw_positions_response = raw_positions if isinstance(raw_positions, dict) else {"raw": raw_positions}
            rt.raw_tradebook_response = raw_tradebook if isinstance(raw_tradebook, dict) else {"raw": raw_tradebook}

        positions = rt.rest_client.parse_positions(raw_positions)
        trades = rt.rest_client.parse_tradebook(raw_tradebook)

        with self._lock:
            rt.last_refresh_epoch = time.time()
            rt.last_error = ""
            rt.positions = positions
            rt.trades = trades

            for pos in rt.positions:
                symbol = pos["symbol"]
                if pos["ltp"] > 0:
                    rt.ltp_cache[symbol] = pos["ltp"]
                else:
                    pos["ltp"] = rt.ltp_cache.get(symbol, pos["avg_price"])

            realized = compute_realized_from_trades(rt.trades)
            day_realized = compute_day_realized_from_trades(rt.trades, tz_name=self.market_timezone)
            rt.pnl = compute_trader_totals(rt.positions, realized, day_realized)

            self.repository.replace_positions(
                rt.config.id,
                (
                    (
                        p["symbol"],
                        int(p["quantity"]),
                        float(p["avg_price"]),
                        str(p["side"]),
                        float(p["ltp"]),
                    )
                    for p in rt.positions
                ),
            )
            self.repository.replace_trades(
                rt.config.id,
                (
                    (
                        t["symbol"],
                        int(t["qty"]),
                        float(t["price"]),
                        str(t["side"]),
                        str(t["timestamp"]),
                    )
                    for t in rt.trades
                ),
            )
            self.repository.insert_pnl_snapshot(
                rt.config.id,
                rt.pnl["current_pnl"],
                rt.pnl["realized_pnl"],
                rt.pnl["day_realized_pnl"],
                rt.pnl["total_pnl"],
            )

            if self.websocket_enabled:
                self._ensure_socket(rt)

    def _ensure_socket(self, rt: TraderRuntime) -> None:
        symbols = {p["symbol"] for p in rt.positions if p.get("symbol")}
        if symbols == rt.socket_symbols:
            return

        if rt.socket:
            rt.socket.close()

        rt.socket_symbols = symbols
        if not symbols:
            rt.socket = None
            return

        def _on_ltp(symbol: str, ltp: float) -> None:
            with self._lock:
                rt.ltp_cache[symbol] = ltp
                for p in rt.positions:
                    if p["symbol"] == symbol:
                        p["ltp"] = ltp
                realized = compute_realized_from_trades(rt.trades)
                day_realized = compute_day_realized_from_trades(rt.trades, tz_name=self.market_timezone)
                rt.pnl = compute_trader_totals(rt.positions, realized, day_realized)
                self.repository.replace_positions(
                    rt.config.id,
                    (
                        (
                            p["symbol"],
                            int(p["quantity"]),
                            float(p["avg_price"]),
                            str(p["side"]),
                            float(p["ltp"]),
                        )
                        for p in rt.positions
                    ),
                )
                self.repository.insert_pnl_snapshot(
                    rt.config.id,
                    rt.pnl["current_pnl"],
                    rt.pnl["realized_pnl"],
                    rt.pnl["day_realized_pnl"],
                    rt.pnl["total_pnl"],
                )

        socket_token = f"{rt.config.client_id}:{rt.access_token}"
        rt.socket = FyersLtpSocket(socket_token, list(symbols), _on_ltp)
        threading.Thread(target=rt.socket.connect, name=f"ltp-socket-{rt.config.id}", daemon=True).start()

    def _with_retry(self, fn, retries: int = 3):
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                return fn()
            except Exception as exc:  # noqa: PERF203
                last_exc = exc
                wait_for = min(2**attempt, 5)
                logger.warning("Call failed (attempt %s/%s): %s", attempt, retries, exc)
                time.sleep(wait_for)
        raise RuntimeError(f"All retries failed: {last_exc}")

    def get_pnl_snapshot(self) -> dict:
        with self._lock:
            traders = []
            for rt in self._traders.values():
                traders.append(
                    {
                        "id": rt.config.id,
                        "name": rt.config.name,
                        "current_pnl": rt.pnl["current_pnl"],
                        "realized_pnl": rt.pnl["realized_pnl"],
                        "day_realized_pnl": rt.pnl["day_realized_pnl"],
                        "total_pnl": rt.pnl["total_pnl"],
                    }
                )

            combined = {
                "current_pnl": round(sum(t["current_pnl"] for t in traders), 2),
                "realized_pnl": round(sum(t["realized_pnl"] for t in traders), 2),
                "day_realized_pnl": round(sum(t["day_realized_pnl"] for t in traders), 2),
                "total_pnl": round(sum(t["total_pnl"] for t in traders), 2),
            }

            return {"traders": traders, "combined": combined}

    def get_positions_view(self) -> list[dict]:
        with self._lock:
            rows = []
            for rt in self._traders.values():
                for pos in rt.positions:
                    side = pos["side"]
                    qty = int(pos["quantity"])
                    avg = float(pos["avg_price"])
                    ltp = float(pos["ltp"])
                    current_pnl = (avg - ltp) * qty if side == "SHORT" else (ltp - avg) * qty
                    rows.append(
                        {
                            "trader_id": rt.config.id,
                            "trader_name": rt.config.name,
                            "symbol": pos["symbol"],
                            "quantity": qty,
                            "avg_price": round(avg, 2),
                            "side": side,
                            "ltp": round(ltp, 2),
                            "current_pnl": round(current_pnl, 2),
                        }
                    )
            return rows

    def get_debug_snapshot(self) -> dict:
        with self._lock:
            traders = []
            for rt in self._traders.values():
                traders.append(
                    {
                        "id": rt.config.id,
                        "name": rt.config.name,
                        "last_refresh_epoch": rt.last_refresh_epoch,
                        "last_attempt_epoch": rt.last_attempt_epoch,
                        "last_error": rt.last_error,
                        "pnl": rt.pnl,
                        "normalized_positions": rt.positions,
                        "normalized_trades": rt.trades,
                        "raw_positions_response": rt.raw_positions_response,
                        "raw_tradebook_response": rt.raw_tradebook_response,
                    }
                )
            return {"traders": traders}
