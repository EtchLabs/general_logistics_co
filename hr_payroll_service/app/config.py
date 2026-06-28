from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "hr_payroll_service"
    service_version: str = "0.1.0"
    log_level: str = "INFO"
    postgres_schema: str = "hr_payroll"
    federal_tax_rate_percent: float = 22.0
    fica_rate_percent: float = 7.65

    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "glc"
    postgres_password: str = "glc_dev_password"
    postgres_db: str = "glc"

    accounting_service_url: str = "http://accounting_service:8010"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
