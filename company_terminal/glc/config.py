from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings:
    api_gateway_url: str = os.getenv("API_GATEWAY_URL", "http://localhost:8080").rstrip("/")
    compose_file: Path = Path(os.getenv("COMPOSE_FILE", PROJECT_ROOT / "docker-compose.yml"))
    compose_project: str = os.getenv("COMPOSE_PROJECT_NAME", "glc")
    refresh_seconds: float = float(os.getenv("TERMINAL_REFRESH_SECONDS", "2.0"))
    log_tail_lines: int = int(os.getenv("TERMINAL_LOG_TAIL", "120"))
    host: str = os.getenv("TERMINAL_HOST", "localhost")


@lru_cache
def get_settings() -> Settings:
    return Settings()
