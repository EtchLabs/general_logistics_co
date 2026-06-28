from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "api_gateway"
    service_version: str = "0.1.0"
    log_level: str = "INFO"
    rate_limit_requests: int = 600
    rate_limit_window_seconds: int = 60

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

    jwt_secret_key: str = "change-me-in-production"

    customer_service_url: str = "http://customer_service:8001"
    product_service_url: str = "http://product_service:8002"
    order_service_url: str = "http://order_service:8003"
    inventory_service_url: str = "http://inventory_service:8004"
    fulfillment_service_url: str = "http://fulfillment_service:8005"
    shipping_service_url: str = "http://shipping_service:8006"
    payment_service_url: str = "http://payment_service:8007"
    tax_service_url: str = "http://tax_service:8008"
    supplier_service_url: str = "http://supplier_service:8009"
    accounting_service_url: str = "http://accounting_service:8010"
    hr_payroll_service_url: str = "http://hr_payroll_service:8011"
    notification_service_url: str = "http://notification_service:8012"
    reporting_service_url: str = "http://reporting_service:8013"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
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
