import logging
import random
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_gateway_url: str = "http://api_gateway:8080"
    simulator_order_interval_min_seconds: float = 5.0
    simulator_order_interval_max_seconds: float = 10.0
    simulator_orders_per_hour: int | None = None
    simulator_variance_pct: int = 25
    simulator_new_customer_pct: int = 12
    simulator_health_port: int = 8020
    log_level: str = "INFO"

    def resolved_order_interval(self) -> tuple[float, float]:
        """Seconds to wait between orders (min, max)."""
        if self.simulator_orders_per_hour is not None:
            base = 3600.0 / max(self.simulator_orders_per_hour, 1)
            spread = base * (self.simulator_variance_pct / 100.0)
            return (max(0.5, base - spread), base + spread)
        lo = min(self.simulator_order_interval_min_seconds, self.simulator_order_interval_max_seconds)
        hi = max(self.simulator_order_interval_min_seconds, self.simulator_order_interval_max_seconds)
        return (lo, hi)

    def estimated_orders_per_hour(self) -> float:
        lo, hi = self.resolved_order_interval()
        return 3600.0 / ((lo + hi) / 2.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()


FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Quinn", "Avery",
    "Blake", "Drew", "Jamie", "Kerry", "Logan", "Parker", "Reese", "Skyler",
]
LAST_NAMES = [
    "Nguyen", "Patel", "Garcia", "Kim", "Johnson", "Martinez", "Chen", "Brown",
    "Wilson", "Anderson", "Thomas", "Jackson", "White", "Harris", "Clark", "Lewis",
]
STREETS = [
    "Oak St", "Maple Ave", "Cedar Ln", "Pine Rd", "Elm Dr", "Birch Way", "Willow Ct",
]
CITIES = [
    ("Portland", "OR", "97201"),
    ("Seattle", "WA", "98101"),
    ("Denver", "CO", "80202"),
    ("Austin", "TX", "78701"),
    ("Chicago", "IL", "60601"),
    ("Atlanta", "GA", "30301"),
    ("Phoenix", "AZ", "85001"),
    ("Boston", "MA", "02108"),
]


def random_customer_payload() -> dict:
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    suffix = random.randint(1000, 9999)
    city, state, postal = random.choice(CITIES)
    return {
        "email": f"{first.lower()}.{last.lower()}.{suffix}@example.com",
        "password": "SimulatorPass123!",
        "first_name": first,
        "last_name": last,
        "phone": f"555-{random.randint(100,999):03d}-{random.randint(1000,9999):04d}",
        "address": {
            "label": "Home",
            "line1": f"{random.randint(100, 9999)} {random.choice(STREETS)}",
            "city": city,
            "state": state,
            "postal_code": postal,
            "country": "US",
            "is_default": True,
        },
    }
