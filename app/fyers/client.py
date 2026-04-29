from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime


logger = logging.getLogger(__name__)


class FyersRestClient:
    def __init__(self, client_id: str, access_token: str) -> None:
        from fyers_apiv3 import fyersModel

        # FyersModel internally builds auth header as "<client_id>:<token>".
        # Pass only the raw access token here.
        self._client = fyersModel.FyersModel(
            client_id=client_id, token=access_token, is_async=False, log_path=""
        )

    def fetch_positions_raw(self) -> dict:
        return self._client.positions()

    def parse_positions(self, response: dict) -> list[dict]:
        if not isinstance(response, dict):
            return []

        rows_raw = response.get("netPositions")
        if rows_raw is None:
            rows_raw = response.get("positions")
        if rows_raw is None:
            rows_raw = []

        if isinstance(rows_raw, dict):
            rows = [rows_raw]
        elif isinstance(rows_raw, list):
            rows = rows_raw
        else:
            rows = []

        result: list[dict] = []

        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                qty = int(row.get("netQty") or row.get("qty") or row.get("netqty") or 0)
                if qty == 0:
                    continue

                symbol = str(row.get("symbol") or row.get("fyToken") or row.get("id"))
                buy_avg = float(row.get("buyAvg") or row.get("avg_price") or row.get("avgPrice") or 0.0)
                sell_avg = float(row.get("sellAvg") or row.get("sell_avg") or 0.0)
                side = "LONG" if qty > 0 else "SHORT"

                if side == "LONG":
                    avg_price = buy_avg if buy_avg > 0 else float(row.get("avgPrice") or 0.0)
                else:
                    avg_price = sell_avg if sell_avg > 0 else float(row.get("avgPrice") or 0.0)

                result.append(
                    {
                        "symbol": symbol,
                        "quantity": abs(qty),
                        "avg_price": avg_price,
                        "side": side,
                        "ltp": float(row.get("ltp") or 0.0),
                    }
                )
            except Exception:
                continue

        return result

    def get_positions(self) -> list[dict]:
        response = self.fetch_positions_raw()
        return self.parse_positions(response)

    def fetch_tradebook_raw(self) -> dict:
        return self._client.tradebook()

    def parse_tradebook(self, response: dict) -> list[dict]:
        if not isinstance(response, dict):
            return []

        rows_raw = response.get("tradeBook")
        if rows_raw is None:
            rows_raw = response.get("trades")
        if rows_raw is None:
            rows_raw = []

        if isinstance(rows_raw, dict):
            rows = [rows_raw]
        elif isinstance(rows_raw, list):
            rows = rows_raw
        else:
            rows = []

        result: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                qty = int(row.get("tradedQty") or row.get("qty") or row.get("filledQty") or 0)
                if qty == 0:
                    continue

                ts = row.get("tradeDate") or row.get("orderDateTime") or datetime.utcnow().isoformat()
                result.append(
                    {
                        "symbol": str(row.get("symbol")),
                        "qty": abs(qty),
                        "price": float(row.get("tradePrice") or row.get("price") or 0.0),
                        "side": str(row.get("side") or row.get("orderType") or "BUY"),
                        "timestamp": str(ts),
                    }
                )
            except Exception:
                continue

        return result

    def get_tradebook(self) -> list[dict]:
        response = self.fetch_tradebook_raw()
        return self.parse_tradebook(response)


class FyersLtpSocket:
    def __init__(
        self,
        access_token: str,
        symbols: list[str],
        on_ltp: Callable[[str, float], None],
    ) -> None:
        self.access_token = access_token
        self.symbols = list(set(symbols))
        self.on_ltp = on_ltp
        self._socket = None

    def connect(self) -> None:
        if not self.symbols:
            return

        from fyers_apiv3.FyersWebsocket import data_ws

        def _on_message(message: dict) -> None:
            symbol = message.get("symbol") or message.get("symbol_name") or message.get("name")
            ltp = message.get("ltp") or message.get("last_traded_price") or message.get("lp")
            if symbol and ltp is not None:
                self.on_ltp(str(symbol), float(ltp))

        def _on_open() -> None:
            try:
                self._socket.subscribe(symbols=self.symbols, data_type="SymbolUpdate")
                self._socket.keep_running()
            except Exception as exc:
                logger.exception("Socket subscribe failed: %s", exc)

        self._socket = data_ws.FyersDataSocket(
            access_token=self.access_token,
            log_path="",
            litemode=True,
            write_to_file=False,
            reconnect=True,
            on_connect=_on_open,
            on_message=_on_message,
            on_close=lambda message: logger.warning("LTP socket closed: %s", message),
            on_error=lambda message: logger.warning("LTP socket error: %s", message),
        )

        self._socket.connect()

    def close(self) -> None:
        if self._socket:
            try:
                self._socket.close_connection()
            except Exception:
                logger.exception("Error closing socket")
