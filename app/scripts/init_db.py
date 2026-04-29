from __future__ import annotations

from app.core.settings import get_settings
from app.db.database import Database
from app.db.schema import init_schema


def main() -> None:
    settings = get_settings()
    db = Database(settings.sqlite_path)
    init_schema(db)
    print(f"Schema initialized at {settings.sqlite_path}")


if __name__ == "__main__":
    main()
