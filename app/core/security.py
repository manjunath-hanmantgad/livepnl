from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet


class TokenStore:
    def __init__(self, key_path: Path, token_store_path: Path) -> None:
        self.key_path = key_path
        self.token_store_path = token_store_path
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_store_path.parent.mkdir(parents=True, exist_ok=True)
        self._fernet = Fernet(self._get_or_create_key())

    def _get_or_create_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes()

        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        os.chmod(self.key_path, 0o600)
        return key

    def _read_store(self) -> dict[str, str]:
        if not self.token_store_path.exists():
            return {}

        encrypted = self.token_store_path.read_bytes()
        if not encrypted:
            return {}

        raw = self._fernet.decrypt(encrypted)
        payload = json.loads(raw.decode("utf-8"))
        return {str(k): str(v) for k, v in payload.items()}

    def _write_store(self, payload: dict[str, str]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        encrypted = self._fernet.encrypt(raw)
        self.token_store_path.write_bytes(encrypted)
        os.chmod(self.token_store_path, 0o600)

    def set_token(self, alias: str, token: str) -> None:
        payload = self._read_store()
        payload[alias] = token
        self._write_store(payload)

    def get_token(self, alias: str) -> str:
        payload = self._read_store()
        token = payload.get(alias)
        if not token:
            raise KeyError(f"Token alias '{alias}' not found in encrypted token store")
        return token
