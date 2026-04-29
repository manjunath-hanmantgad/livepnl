from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.api.schemas import PnlResponse, PositionResponseItem
from app.core.container import get_container


@asynccontextmanager
async def lifespan(_: FastAPI):
    container = get_container()
    container.ingestion.start()
    try:
        yield
    finally:
        container.ingestion.stop()


app = FastAPI(title="Live Multi-Trader PnL", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/pnl", response_model=PnlResponse)
def get_pnl() -> dict:
    container = get_container()
    return container.ingestion.get_pnl_snapshot()


@app.get("/positions", response_model=list[PositionResponseItem])
def get_positions() -> list[dict]:
    container = get_container()
    return container.ingestion.get_positions_view()


@app.get("/debug/raw")
def get_debug_raw() -> dict:
    container = get_container()
    if not container.settings.debug_raw_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    return container.ingestion.get_debug_snapshot()
