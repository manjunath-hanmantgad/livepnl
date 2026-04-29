from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


load_dotenv()


@dataclass
class TraderConfig:
    id: int
    name: str
    client_id: str
    api_key: str
    token_alias: str
    secret_key: str | None = None
    redirect_uri: str | None = None


@dataclass
class AppSettings:
    polling_interval_sec: float
    websocket_enabled: bool
    debug_raw_enabled: bool
    market_timezone: str
    sqlite_path: Path
    traders_file: Path
    secret_key_path: Path
    token_store_path: Path


DEFAULT_TRADERS_PATH = Path(os.getenv("TRADERS_CONFIG_PATH", "config/traders.json"))
DEFAULT_DB_PATH = Path(os.getenv("SQLITE_PATH", "data/live_pnl.db"))
DEFAULT_SECRET_KEY_PATH = Path(os.getenv("SECRET_KEY_PATH", "data/.secret.key"))
DEFAULT_TOKEN_STORE_PATH = Path(os.getenv("TOKEN_STORE_PATH", "data/tokens.enc"))


def get_settings() -> AppSettings:
    return AppSettings(
        polling_interval_sec=float(os.getenv("POLLING_INTERVAL_SEC", "5")),
        websocket_enabled=os.getenv("WEBSOCKET_ENABLED", "true").lower() == "true",
        debug_raw_enabled=os.getenv("DEBUG_RAW_ENABLED", "false").lower() == "true",
        market_timezone=os.getenv("MARKET_TIMEZONE", "Asia/Kolkata"),
        sqlite_path=DEFAULT_DB_PATH,
        traders_file=DEFAULT_TRADERS_PATH,
        secret_key_path=DEFAULT_SECRET_KEY_PATH,
        token_store_path=DEFAULT_TOKEN_STORE_PATH,
    )


def load_traders(path: Path) -> list[TraderConfig]:
    if not path.exists():
        raise FileNotFoundError(
            f"Missing traders config at {path}. Copy config/traders.example.json -> config/traders.json"
        )

    payload: dict[str, Any] = json.loads(path.read_text())
    traders_raw = payload.get("traders", [])
    traders: list[TraderConfig] = []

    for item in traders_raw:
        traders.append(
            TraderConfig(
                id=int(item["id"]),
                name=str(item["name"]),
                client_id=str(item["client_id"]),
                api_key=str(item.get("api_key", item["client_id"])),
                token_alias=str(item["token_alias"]),
                secret_key=(str(item["secret_key"]) if item.get("secret_key") else None),
                redirect_uri=(str(item["redirect_uri"]) if item.get("redirect_uri") else None),
            )
        )

    if not traders:
        raise ValueError(f"No traders configured in {path}")

    return traders
