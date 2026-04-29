from __future__ import annotations

from collections.abc import Iterable

from app.db.database import Database


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert_trader(self, trader_id: int, name: str, api_key: str, access_token: str) -> None:
        self.db.execute(
            """
            INSERT INTO traders (id, name, api_key, access_token)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                api_key=excluded.api_key,
                access_token=excluded.access_token
            """,
            (trader_id, name, api_key, access_token),
        )

    def replace_positions(self, trader_id: int, rows: Iterable[tuple[str, int, float, str, float]]) -> None:
        self.db.execute("DELETE FROM positions WHERE trader_id = ?", (trader_id,))
        params = [(trader_id, symbol, qty, avg_price, side, ltp) for symbol, qty, avg_price, side, ltp in rows]
        if params:
            self.db.executemany(
                """
                INSERT INTO positions (trader_id, symbol, quantity, avg_price, side, ltp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                params,
            )

    def replace_trades(self, trader_id: int, rows: Iterable[tuple[str, int, float, str, str]]) -> None:
        self.db.execute("DELETE FROM trades WHERE trader_id = ?", (trader_id,))
        params = [(trader_id, symbol, qty, price, side, timestamp) for symbol, qty, price, side, timestamp in rows]
        if params:
            self.db.executemany(
                """
                INSERT INTO trades (trader_id, symbol, qty, price, side, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                params,
            )

    def insert_pnl_snapshot(
        self,
        trader_id: int,
        current_pnl: float,
        realized_pnl: float,
        day_realized_pnl: float,
        total_pnl: float,
    ) -> None:
        self.db.execute(
            """
            INSERT INTO pnl_snapshot (trader_id, current_pnl, realized_pnl, day_realized_pnl, total_pnl)
            VALUES (?, ?, ?, ?, ?)
            """,
            (trader_id, current_pnl, realized_pnl, day_realized_pnl, total_pnl),
        )

    def get_latest_pnl(self) -> list[dict]:
        rows = self.db.query_all(
            """
            SELECT p1.trader_id, p1.current_pnl, p1.realized_pnl, p1.day_realized_pnl, p1.total_pnl, p1.timestamp
            FROM pnl_snapshot p1
            INNER JOIN (
                SELECT trader_id, MAX(id) AS max_id
                FROM pnl_snapshot
                GROUP BY trader_id
            ) p2
            ON p1.id = p2.max_id
            """
        )
        return [dict(row) for row in rows]

    def get_positions(self) -> list[dict]:
        rows = self.db.query_all(
            """
            SELECT p.trader_id, t.name AS trader_name, p.symbol, p.quantity, p.avg_price, p.side, p.ltp, p.timestamp
            FROM positions p
            INNER JOIN traders t ON p.trader_id = t.id
            ORDER BY p.trader_id, p.symbol
            """
        )
        return [dict(row) for row in rows]
