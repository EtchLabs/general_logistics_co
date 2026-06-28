import logging
import random
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_gateway_url: str = "http://api_gateway:8080"
    supplier_poll_interval_seconds: int = 30
    supplier_lead_time_days_min: int = 2
    supplier_lead_time_days_max: int = 7
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


logger = logging.getLogger(__name__)


def simulate_shipment_behavior() -> dict:
    """Return simulated supplier response metadata."""
    roll = random.random()
    if roll < 0.05:
        return {"status": "partial", "fill_rate": round(random.uniform(0.5, 0.9), 2)}
    if roll < 0.08:
        return {"status": "backorder", "fill_rate": 0.0}
    if roll < 0.10:
        return {"status": "quantity_mismatch", "fill_rate": round(random.uniform(0.9, 1.1), 2)}
    return {"status": "confirmed", "fill_rate": 1.0}
