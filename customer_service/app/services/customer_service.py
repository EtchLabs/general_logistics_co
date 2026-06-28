from datetime import UTC, datetime, timedelta
from uuid import UUID

from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.mongo import get_mongo_db
from app.models.postgres import (
    Address,
    Customer,
    LoyaltyTier,
    PaymentMethod,
    SupportTicket,
    TicketStatus,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(customer_id: UUID) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(customer_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def log_activity(
    customer_id: UUID,
    action: str,
    metadata: dict | None = None,
    correlation_id: str | None = None,
) -> None:
    db = get_mongo_db()
    doc = {
        "customer_id": str(customer_id),
        "action": action,
        "metadata": metadata or {},
        "correlation_id": correlation_id,
        "created_at": datetime.now(UTC),
    }
    await db.customer_activity_logs.insert_one(doc)


async def get_customer_or_404(session: AsyncSession, customer_id: UUID) -> Customer:
    result = await session.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if customer is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


async def get_customer_by_email_or_404(session: AsyncSession, email: str) -> Customer:
    result = await session.execute(select(Customer).where(Customer.email == email.lower()))
    customer = result.scalar_one_or_none()
    if customer is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


async def clear_default_addresses(session: AsyncSession, customer_id: UUID) -> None:
    await session.execute(
        update(Address)
        .where(Address.customer_id == customer_id, Address.is_default.is_(True))
        .values(is_default=False)
    )


async def clear_default_payment_methods(session: AsyncSession, customer_id: UUID) -> None:
    await session.execute(
        update(PaymentMethod)
        .where(PaymentMethod.customer_id == customer_id, PaymentMethod.is_default.is_(True))
        .values(is_default=False)
    )


def tokenize_card(card_number: str) -> tuple[str, str]:
    digits = "".join(c for c in card_number if c.isdigit())
    token = f"tok_{digits[-8:]}"
    return token, digits[-4:]


async def ensure_mongo_indexes() -> None:
    db = get_mongo_db()
    await db.customer_activity_logs.create_index([("customer_id", 1), ("created_at", -1)])
    await db.customer_preferences.create_index("customer_id", unique=True)
    await db.support_ticket_messages.create_index([("ticket_id", 1), ("created_at", 1)])
