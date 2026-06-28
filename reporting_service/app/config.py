from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "reporting_service"
    service_version: str = "0.1.0"
    log_level: str = "INFO"
    cache_ttl_seconds: int = 300

    mongo_host: str = "mongo"
    mongo_port: int = 27017
    mongo_user: str = "glc"
    mongo_password: str = "glc_dev_password"
    mongo_db: str = "glc"

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_url: str = "redis://redis:6379/0"

    order_service_url: str = "http://order_service:8003"
    product_service_url: str = "http://product_service:8002"

    @property
    def mongo_uri(self) -> str:
        return (
            f"mongodb://{self.mongo_user}:{self.mongo_password}"
            f"@{self.mongo_host}:{self.mongo_port}/{self.mongo_db}?authSource=admin"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
