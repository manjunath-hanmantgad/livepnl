from __future__ import annotations

import logging

from app.core.security import TokenStore
from app.core.settings import get_settings, load_traders
from app.db.database import Database
from app.db.repository import Repository
from app.db.schema import init_schema
from app.services.ingestion import IngestionService


logger = logging.getLogger(__name__)


class AppContainer:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.token_store = TokenStore(
            key_path=self.settings.secret_key_path,
            token_store_path=self.settings.token_store_path,
        )
        self.db = Database(self.settings.sqlite_path)
        init_schema(self.db)
        self.repo = Repository(self.db)
        self.ingestion = self._build_ingestion_service()

    def _build_ingestion_service(self) -> IngestionService:
        traders = load_traders(self.settings.traders_file)
        trader_tokens: list[tuple] = []
        for trader in traders:
            try:
                token = self.token_store.get_token(trader.token_alias)
            except KeyError:
                logger.warning(
                    "Skipping trader id=%s alias=%s because token is missing",
                    trader.id,
                    trader.token_alias,
                )
                continue
            trader_tokens.append((trader, token))

        if not trader_tokens:
            raise RuntimeError(
                "No trader tokens available. Add at least one token with "
                "`python fyers_auth.py --alias <token_alias> --manual`."
            )

        return IngestionService(
            trader_tokens=trader_tokens,
            repository=self.repo,
            polling_interval_sec=self.settings.polling_interval_sec,
            websocket_enabled=self.settings.websocket_enabled,
            market_timezone=self.settings.market_timezone,
        )


container: AppContainer | None = None


def get_container() -> AppContainer:
    global container
    if container is None:
        container = AppContainer()
    return container
