"""Generate realistic, varied shopping carts for the customer simulator."""

from __future__ import annotations

import random
from typing import Any


# Weighted order shapes — multi-item, bulk lines, singles, etc.
_PROFILES: list[tuple[str, float]] = [
    ("single", 0.18),
    ("pair", 0.14),
    ("multi_mixed", 0.28),
    ("bulk_single", 0.16),
    ("mixed_bulk", 0.14),
    ("wholesale", 0.10),
]

_PREMIUM_PREFIX = ("WDG-006", "WDG-007", "WDG-008", "WDG-009")
_INDUSTRIAL_PREFIX = ("WDG-010", "WDG-011", "WDG-012")


def _pick(skus: list[str], pool: list[str] | None = None) -> str:
    choices = [s for s in (pool or skus) if s in skus]
    return random.choice(choices or skus)


def _sample_unique(skus: list[str], count: int) -> list[str]:
    return random.sample(skus, min(count, len(skus)))


def build_random_cart(skus: list[str]) -> list[dict[str, Any]]:
    """Return line_items with varied SKUs and quantities."""
    if not skus:
        return []

    profile = random.choices(
        [name for name, _ in _PROFILES],
        weights=[weight for _, weight in _PROFILES],
    )[0]

    premium = [s for s in skus if any(s.startswith(p) for p in _PREMIUM_PREFIX)]
    industrial = [s for s in skus if any(s.startswith(p) for p in _INDUSTRIAL_PREFIX)]
    budget = [s for s in skus if s not in premium and s not in industrial]

    if profile == "single":
        return [{"sku": _pick(skus, budget or skus), "quantity": 1}]

    if profile == "pair":
        sku = _pick(skus, budget or skus)
        return [{"sku": sku, "quantity": random.randint(2, 4)}]

    if profile == "multi_mixed":
        lines: list[dict[str, Any]] = []
        for sku in _sample_unique(skus, random.randint(2, 5)):
            lines.append({"sku": sku, "quantity": random.randint(1, 3)})
        return lines

    if profile == "bulk_single":
        sku = _pick(skus, industrial or premium or skus)
        return [{"sku": sku, "quantity": random.randint(6, 24)}]

    if profile == "mixed_bulk":
        chosen = _sample_unique(skus, random.randint(3, 6))
        bulk_sku = _pick(chosen, industrial or premium or chosen)
        lines = []
        for sku in chosen:
            if sku == bulk_sku:
                lines.append({"sku": sku, "quantity": random.randint(4, 18)})
            else:
                lines.append({"sku": sku, "quantity": random.randint(1, 2)})
        return lines

    # wholesale — many lines, higher quantities on industrial SKUs
    line_count = random.randint(4, min(9, len(skus)))
    chosen = _sample_unique(skus, line_count)
    lines = []
    for sku in chosen:
        if sku in industrial:
            qty = random.randint(8, 30)
        elif sku in premium:
            qty = random.randint(2, 8)
        else:
            qty = random.randint(1, 6)
        lines.append({"sku": sku, "quantity": qty})
    return lines


def random_shipping_total() -> str:
    return random.choice(["0.00", "0.00", "5.99", "5.99", "9.99", "12.99"])
