#!/bin/sh
set -e
python - <<'PY'
from sqlalchemy import create_engine, text

from app.config import get_settings

settings = get_settings()
engine = create_engine(settings.postgres_dsn)
with engine.begin() as conn:
    conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {settings.postgres_schema}"))
PY
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8002
