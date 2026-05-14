"""Database URL resolution for local and Railway environments."""

import os
from urllib.parse import quote


DEFAULT_DATABASE_URL = "sqlite:///feedback_runs.db"


def resolve_database_url(default_url: str = DEFAULT_DATABASE_URL) -> str:
    direct_url = (os.getenv("DATABASE_URL") or "").strip()
    if direct_url:
        return direct_url

    public_url = (os.getenv("DATABASE_PUBLIC_URL") or "").strip()
    if public_url:
        return public_url

    pg_url = _database_url_from_pg_vars()
    if pg_url:
        return pg_url

    if os.getenv("RAILWAY_ENVIRONMENT_ID"):
        raise RuntimeError(
            "Railway 서비스에 DATABASE_URL이 비어 있습니다. "
            "서비스 Variables에서 DATABASE_URL을 Postgres의 DATABASE_URL reference로 다시 연결해주세요."
        )
    return default_url


def _database_url_from_pg_vars() -> str:
    host = (os.getenv("PGHOST") or "").strip()
    port = (os.getenv("PGPORT") or "5432").strip()
    user = (os.getenv("PGUSER") or "").strip()
    password = os.getenv("PGPASSWORD") or os.getenv("POSTGRES_PASSWORD") or ""
    database = (os.getenv("PGDATABASE") or "").strip()

    if not all([host, port, user, password, database]):
        return ""

    return (
        f"postgresql://{quote(user)}:{quote(password)}"
        f"@{host}:{port}/{quote(database)}"
    )
