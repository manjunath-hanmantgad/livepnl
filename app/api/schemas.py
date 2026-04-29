from __future__ import annotations

from pydantic import BaseModel


class TraderPnl(BaseModel):
    id: int
    name: str
    current_pnl: float
    realized_pnl: float
    day_realized_pnl: float
    total_pnl: float


class CombinedPnl(BaseModel):
    current_pnl: float
    realized_pnl: float
    day_realized_pnl: float
    total_pnl: float


class PnlResponse(BaseModel):
    traders: list[TraderPnl]
    combined: CombinedPnl


class PositionResponseItem(BaseModel):
    trader_id: int
    trader_name: str
    symbol: str
    quantity: int
    avg_price: float
    side: str
    ltp: float
    current_pnl: float
