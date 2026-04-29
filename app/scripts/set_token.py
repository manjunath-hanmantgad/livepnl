from __future__ import annotations

import argparse
import getpass

from app.core.security import TokenStore
from app.core.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Store FYERS access token in encrypted local store")
    parser.add_argument("alias", help="token alias, for example trader1")
    parser.add_argument("--token", help="access token (if omitted, prompt securely)")
    args = parser.parse_args()

    token = args.token or getpass.getpass("Access token: ")
    settings = get_settings()
    store = TokenStore(settings.secret_key_path, settings.token_store_path)
    store.set_token(args.alias, token)
    print(f"Stored token for alias '{args.alias}' in encrypted local store")


if __name__ == "__main__":
    main()
