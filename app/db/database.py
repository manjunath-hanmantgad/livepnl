from __future__ import annotations

import sqlite3
from pathlib import Path


class Database:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def execute(self, sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()
        return cur

    def executemany(self, sql: str, seq_of_params: list[tuple]) -> None:
        cur = self.conn.cursor()
        cur.executemany(sql, seq_of_params)
        self.conn.commit()

    def query_all(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def query_one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()
