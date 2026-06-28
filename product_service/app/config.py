from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "product_service"
    service_version: str = "0.1.0"
    log_level: str = "INFO"
    postgres_schema: str = "products_pricing"
    cache_ttl_seconds: int = 300

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "glc"
    postgres_password: str = "glc_dev_password"
    postgres_db: str = "glc"

    mongo_host: str = "mongo"
    mongo_port: int = 27017
    mongo_user: str = "glc"
    mongo_password: str = "glc_dev_password"
    mongo_db: str = "glc"

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_url: str = "redis://redis:6379/0"

    supplier_service_url: str = "http://supplier_service:8009"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def mongo_uri(self) -> str:
        return (
            f"mongodb://{self.mongo_user}:{self.mongo_password}"
            f"@{self.mongo_host}:{self.mongo_port}/{self.mongo_db}?authSource=admin"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
