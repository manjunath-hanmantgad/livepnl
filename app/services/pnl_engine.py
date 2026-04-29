from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def compute_unrealized(side: str, avg_price: float, ltp: float, quantity: int) -> float:
    qty = abs(quantity)
    if side == "SHORT":
        return (avg_price - ltp) * qty
    return (ltp - avg_price) * qty


def _is_buy(raw_side: str) -> bool:
    side = raw_side.upper()
    return side in {"BUY", "LONG", "1"}


def _compute_realized_inventory(trades: list[dict]) -> float:
    # Inventory method: realize P&L only when an incoming trade closes existing quantity.
    # `net_qty` > 0 means long inventory, < 0 means short inventory.
    state: dict[str, dict[str, float]] = {}
    realized_total = 0.0

    for tr in trades:
        symbol = str(tr["symbol"])
        qty = abs(int(tr["qty"]))
        price = float(tr["price"])
        is_buy = _is_buy(str(tr["side"]))

        if symbol not in state:
            state[symbol] = {"net_qty": 0.0, "avg_price": 0.0}

        net_qty = float(state[symbol]["net_qty"])
        avg_price = float(state[symbol]["avg_price"])

        if is_buy:
            if net_qty < 0:
                close_qty = min(qty, int(abs(net_qty)))
                realized_total += (avg_price - price) * close_qty
                net_qty += close_qty
                qty -= close_qty
            if qty > 0:
                if net_qty > 0:
                    avg_price = ((net_qty * avg_price) + (qty * price)) / (net_qty + qty)
                else:
                    avg_price = price
                net_qty += qty
        else:
            if net_qty > 0:
                close_qty = min(qty, int(net_qty))
                realized_total += (price - avg_price) * close_qty
                net_qty -= close_qty
                qty -= close_qty
            if qty > 0:
                if net_qty < 0:
                    abs_net = abs(net_qty)
                    avg_price = ((abs_net * avg_price) + (qty * price)) / (abs_net + qty)
                else:
                    avg_price = price
                net_qty -= qty

        if net_qty == 0:
            avg_price = 0.0

        state[symbol]["net_qty"] = net_qty
        state[symbol]["avg_price"] = avg_price

    return round(realized_total, 2)


def _parse_trade_timestamp(raw_ts: str) -> datetime | None:
    text = (raw_ts or "").strip()
    if not text:
        return None

    if text.isdigit():
        value = int(text)
        if value > 10_000_000_000:
            return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        return datetime.fromtimestamp(value, tz=timezone.utc)

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y",
    ):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    return None


def _filter_trades_for_local_day(trades: list[dict], tz_name: str) -> list[dict]:
    tz = ZoneInfo(tz_name)
    today_local = datetime.now(tz).date()
    filtered: list[dict] = []

    for tr in trades:
        parsed = _parse_trade_timestamp(str(tr.get("timestamp", "")))
        if parsed is None:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        local_dt = parsed.astimezone(tz)
        if local_dt.date() == today_local:
            filtered.append(tr)

    return filtered


def compute_realized_from_trades(trades: list[dict]) -> float:
    return _compute_realized_inventory(trades)


def compute_day_realized_from_trades(trades: list[dict], tz_name: str = "Asia/Kolkata") -> float:
    day_trades = _filter_trades_for_local_day(trades, tz_name)
    return _compute_realized_inventory(day_trades)


def compute_trader_totals(positions: list[dict], realized_pnl: float, day_realized_pnl: float) -> dict[str, float]:
    current = 0.0
    for pos in positions:
        current += compute_unrealized(
            side=pos["side"],
            avg_price=float(pos["avg_price"]),
            ltp=float(pos["ltp"]),
            quantity=int(pos["quantity"]),
        )

    total = current + realized_pnl
    return {
        "current_pnl": round(current, 2),
        "realized_pnl": round(realized_pnl, 2),
        "day_realized_pnl": round(day_realized_pnl, 2),
        "total_pnl": round(total, 2),
    }
