from __future__ import annotations

from app.db.database import Database


def init_schema(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS traders (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            api_key TEXT NOT NULL,
            access_token TEXT
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS positions (
            trader_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            avg_price REAL NOT NULL,
            side TEXT NOT NULL,
            ltp REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (trader_id, symbol)
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            trader_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            side TEXT NOT NULL,
            timestamp DATETIME NOT NULL
        )
        """
    )

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS pnl_snapshot (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trader_id INTEGER NOT NULL,
            current_pnl REAL NOT NULL,
            realized_pnl REAL NOT NULL,
            day_realized_pnl REAL NOT NULL DEFAULT 0,
            total_pnl REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    existing_cols = {row["name"] for row in db.query_all("PRAGMA table_info(pnl_snapshot)")}
    if "day_realized_pnl" not in existing_cols:
        db.execute("ALTER TABLE pnl_snapshot ADD COLUMN day_realized_pnl REAL NOT NULL DEFAULT 0")
