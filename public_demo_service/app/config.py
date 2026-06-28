from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "public_demo_service"
    service_version: str = "0.1.0"
    log_level: str = "INFO"
    api_gateway_url: str = "http://api_gateway:8080"
    redis_url: str = "redis://redis:6379/0"
    redis_channel_pattern: str = "orders.*"
    activity_history_limit: int = 80


@lru_cache
def get_settings() -> Settings:
    return Settings()
