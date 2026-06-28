from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.mongo import get_mongo_db
from app.db.postgres import get_session
from app.models.postgres import Address, Customer, PaymentMethod, SupportTicket, TicketStatus
from app.models.schemas import (
    ActivityLogOut,
    AccountStatementLine,
    AddressCreate,
    AddressOut,
    AddressUpdate,
    CustomerLogin,
    CustomerOut,
    CustomerRegister,
    CustomerTagsOut,
    CustomerTagsUpdate,
    CustomerUpdate,
    PasswordResetRequest,
    PaymentMethodCreate,
    PaymentMethodOut,
    PreferencesOut,
    PreferencesUpdate,
    PurchaseHistoryItem,
    SupportTicketCreate,
    SupportTicketOut,
    SupportTicketUpdate,
    TicketMessageCreate,
    TicketMessageOut,
    TokenOut,
)
from app.services.customer_service import (
    clear_default_addresses,
    clear_default_payment_methods,
    create_access_token,
    get_customer_by_email_or_404,
    get_customer_or_404,
    hash_password,
    log_activity,
    tokenize_card,
    verify_password,
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("/register", response_model=TokenOut, status_code=201)
async def register_customer(
    payload: CustomerRegister,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    existing = await session.execute(select(Customer).where(Customer.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    customer = Customer(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone=payload.phone,
    )
    session.add(customer)
    await session.commit()
    await session.refresh(customer)

    db = get_mongo_db()
    await db.customer_preferences.insert_one(
        {"customer_id": str(customer.id), "preferences": {"marketing_emails": True}}
    )
    await log_activity(
        customer.id,
        "customer.registered",
        {"email": customer.email},
        getattr(request.state, "correlation_id", None),
    )

    token = create_access_token(customer.id)
    return TokenOut(access_token=token, customer=CustomerOut.model_validate(customer))


@router.post("/login", response_model=TokenOut)
async def login_customer(
    payload: CustomerLogin,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    result = await session.execute(select(Customer).where(Customer.email == payload.email.lower()))
    customer = result.scalar_one_or_none()
    if customer is None or not verify_password(payload.password, customer.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not customer.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    await log_activity(
        customer.id,
        "customer.login",
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    return TokenOut(access_token=create_access_token(customer.id), customer=CustomerOut.model_validate(customer))


@router.post("/password-reset/request")
async def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    result = await session.execute(select(Customer).where(Customer.email == payload.email.lower()))
    customer = result.scalar_one_or_none()
    if customer:
        await log_activity(
            customer.id,
            "customer.password_reset_requested",
            correlation_id=getattr(request.state, "correlation_id", None),
        )
    return {"message": "If the email exists, reset instructions will be sent."}


@router.get("/by-email/{email}", response_model=CustomerOut)
async def get_customer_by_email_path(
    email: str,
    session: AsyncSession = Depends(get_session),
) -> CustomerOut:
    customer = await get_customer_by_email_or_404(session, email)
    return CustomerOut.model_validate(customer)


@router.get("", response_model=CustomerOut)
async def get_customer_by_email_query(
    email: str,
    session: AsyncSession = Depends(get_session),
) -> CustomerOut:
    customer = await get_customer_by_email_or_404(session, email)
    return CustomerOut.model_validate(customer)


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> CustomerOut:
    customer = await get_customer_or_404(session, customer_id)
    return CustomerOut.model_validate(customer)


@router.patch("/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CustomerOut:
    customer = await get_customer_or_404(session, customer_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await session.commit()
    await session.refresh(customer)
    await log_activity(
        customer.id,
        "customer.updated",
        payload.model_dump(exclude_unset=True),
        getattr(request.state, "correlation_id", None),
    )
    return CustomerOut.model_validate(customer)


@router.get("/{customer_id}/tags", response_model=CustomerTagsOut)
async def get_customer_tags(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> CustomerTagsOut:
    customer = await get_customer_or_404(session, customer_id)
    return CustomerTagsOut(
        customer_id=customer.id,
        loyalty_tier=customer.loyalty_tier,
        is_wholesale=customer.is_wholesale,
    )


@router.patch("/{customer_id}/tags", response_model=CustomerTagsOut)
async def update_customer_tags(
    customer_id: UUID,
    payload: CustomerTagsUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> CustomerTagsOut:
    customer = await get_customer_or_404(session, customer_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    await session.commit()
    await session.refresh(customer)
    await log_activity(
        customer.id,
        "customer.tags_updated",
        payload.model_dump(exclude_unset=True),
        getattr(request.state, "correlation_id", None),
    )
    return CustomerTagsOut(
        customer_id=customer.id,
        loyalty_tier=customer.loyalty_tier,
        is_wholesale=customer.is_wholesale,
    )


@router.post("/{customer_id}/addresses", response_model=AddressOut, status_code=201)
async def create_address(
    customer_id: UUID,
    payload: AddressCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AddressOut:
    await get_customer_or_404(session, customer_id)
    if payload.is_default:
        await clear_default_addresses(session, customer_id)
    address = Address(customer_id=customer_id, **payload.model_dump())
    session.add(address)
    await session.commit()
    await session.refresh(address)
    await log_activity(
        customer_id,
        "address.created",
        {"address_id": str(address.id)},
        getattr(request.state, "correlation_id", None),
    )
    return AddressOut.model_validate(address)


@router.get("/{customer_id}/addresses", response_model=list[AddressOut])
async def list_addresses(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[AddressOut]:
    await get_customer_or_404(session, customer_id)
    result = await session.execute(select(Address).where(Address.customer_id == customer_id))
    return [AddressOut.model_validate(a) for a in result.scalars().all()]


@router.patch("/{customer_id}/addresses/{address_id}", response_model=AddressOut)
async def update_address(
    customer_id: UUID,
    address_id: UUID,
    payload: AddressUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AddressOut:
    await get_customer_or_404(session, customer_id)
    result = await session.execute(
        select(Address).where(Address.id == address_id, Address.customer_id == customer_id)
    )
    address = result.scalar_one_or_none()
    if address is None:
        raise HTTPException(status_code=404, detail="Address not found")
    if payload.is_default:
        await clear_default_addresses(session, customer_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(address, field, value)
    await session.commit()
    await session.refresh(address)
    await log_activity(
        customer_id,
        "address.updated",
        {"address_id": str(address_id)},
        getattr(request.state, "correlation_id", None),
    )
    return AddressOut.model_validate(address)


@router.delete("/{customer_id}/addresses/{address_id}", status_code=204)
async def delete_address(
    customer_id: UUID,
    address_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> None:
    await get_customer_or_404(session, customer_id)
    result = await session.execute(
        select(Address).where(Address.id == address_id, Address.customer_id == customer_id)
    )
    address = result.scalar_one_or_none()
    if address is None:
        raise HTTPException(status_code=404, detail="Address not found")
    await session.delete(address)
    await session.commit()
    await log_activity(
        customer_id,
        "address.deleted",
        {"address_id": str(address_id)},
        getattr(request.state, "correlation_id", None),
    )


@router.post("/{customer_id}/payment-methods", response_model=PaymentMethodOut, status_code=201)
async def create_payment_method(
    customer_id: UUID,
    payload: PaymentMethodCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> PaymentMethodOut:
    await get_customer_or_404(session, customer_id)
    token, last_four = tokenize_card(payload.card_number)
    if payload.is_default:
        await clear_default_payment_methods(session, customer_id)
    pm = PaymentMethod(
        customer_id=customer_id,
        label=payload.label,
        token=token,
        last_four=last_four,
        card_brand=payload.card_brand,
        exp_month=payload.exp_month,
        exp_year=payload.exp_year,
        is_default=payload.is_default,
    )
    session.add(pm)
    await session.commit()
    await session.refresh(pm)
    await log_activity(
        customer_id,
        "payment_method.created",
        {"payment_method_id": str(pm.id), "last_four": last_four},
        getattr(request.state, "correlation_id", None),
    )
    return PaymentMethodOut.model_validate(pm)


@router.get("/{customer_id}/payment-methods", response_model=list[PaymentMethodOut])
async def list_payment_methods(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[PaymentMethodOut]:
    await get_customer_or_404(session, customer_id)
    result = await session.execute(
        select(PaymentMethod).where(PaymentMethod.customer_id == customer_id)
    )
    return [PaymentMethodOut.model_validate(pm) for pm in result.scalars().all()]


@router.delete("/{customer_id}/payment-methods/{payment_method_id}", status_code=204)
async def delete_payment_method(
    customer_id: UUID,
    payment_method_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> None:
    await get_customer_or_404(session, customer_id)
    result = await session.execute(
        select(PaymentMethod).where(
            PaymentMethod.id == payment_method_id,
            PaymentMethod.customer_id == customer_id,
        )
    )
    pm = result.scalar_one_or_none()
    if pm is None:
        raise HTTPException(status_code=404, detail="Payment method not found")
    await session.delete(pm)
    await session.commit()
    await log_activity(
        customer_id,
        "payment_method.deleted",
        {"payment_method_id": str(payment_method_id)},
        getattr(request.state, "correlation_id", None),
    )


@router.post("/{customer_id}/support-tickets", response_model=SupportTicketOut, status_code=201)
async def create_support_ticket(
    customer_id: UUID,
    payload: SupportTicketCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> SupportTicketOut:
    await get_customer_or_404(session, customer_id)
    ticket = SupportTicket(customer_id=customer_id, **payload.model_dump())
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)
    db = get_mongo_db()
    await db.support_ticket_messages.insert_one(
        {
            "ticket_id": str(ticket.id),
            "customer_id": str(customer_id),
            "message": payload.description,
            "author_type": "customer",
            "created_at": ticket.created_at,
        }
    )
    await log_activity(
        customer_id,
        "support_ticket.created",
        {"ticket_id": str(ticket.id)},
        getattr(request.state, "correlation_id", None),
    )
    return SupportTicketOut.model_validate(ticket)


@router.get("/{customer_id}/support-tickets", response_model=list[SupportTicketOut])
async def list_support_tickets(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[SupportTicketOut]:
    await get_customer_or_404(session, customer_id)
    result = await session.execute(
        select(SupportTicket).where(SupportTicket.customer_id == customer_id)
    )
    return [SupportTicketOut.model_validate(t) for t in result.scalars().all()]


@router.get("/{customer_id}/support-tickets/{ticket_id}", response_model=SupportTicketOut)
async def get_support_ticket(
    customer_id: UUID,
    ticket_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> SupportTicketOut:
    await get_customer_or_404(session, customer_id)
    result = await session.execute(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id,
            SupportTicket.customer_id == customer_id,
        )
    )
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    return SupportTicketOut.model_validate(ticket)


@router.patch("/{customer_id}/support-tickets/{ticket_id}", response_model=SupportTicketOut)
async def update_support_ticket(
    customer_id: UUID,
    ticket_id: UUID,
    payload: SupportTicketUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> SupportTicketOut:
    await get_customer_or_404(session, customer_id)
    result = await session.execute(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id,
            SupportTicket.customer_id == customer_id,
        )
    )
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ticket, field, value)
    if payload.status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
        from datetime import UTC, datetime

        ticket.closed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(ticket)
    await log_activity(
        customer_id,
        "support_ticket.updated",
        {"ticket_id": str(ticket_id), **payload.model_dump(exclude_unset=True)},
        getattr(request.state, "correlation_id", None),
    )
    return SupportTicketOut.model_validate(ticket)


@router.post(
    "/{customer_id}/support-tickets/{ticket_id}/messages",
    response_model=TicketMessageOut,
    status_code=201,
)
async def add_ticket_message(
    customer_id: UUID,
    ticket_id: UUID,
    payload: TicketMessageCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TicketMessageOut:
    await get_customer_or_404(session, customer_id)
    result = await session.execute(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id,
            SupportTicket.customer_id == customer_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")

    from datetime import UTC, datetime

    doc = {
        "ticket_id": str(ticket_id),
        "customer_id": str(customer_id),
        "message": payload.message,
        "author_type": "customer",
        "created_at": datetime.now(UTC),
    }
    inserted = await get_mongo_db().support_ticket_messages.insert_one(doc)
    await log_activity(
        customer_id,
        "support_ticket.message_added",
        {"ticket_id": str(ticket_id)},
        getattr(request.state, "correlation_id", None),
    )
    return TicketMessageOut(
        id=str(inserted.inserted_id),
        ticket_id=ticket_id,
        customer_id=customer_id,
        message=payload.message,
        author_type="customer",
        created_at=doc["created_at"],
    )


@router.get("/{customer_id}/activity", response_model=list[ActivityLogOut])
async def list_activity(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[ActivityLogOut]:
    await get_customer_or_404(session, customer_id)
    cursor = (
        get_mongo_db()
        .customer_activity_logs.find({"customer_id": str(customer_id)})
        .sort("created_at", -1)
        .limit(100)
    )
    logs: list[ActivityLogOut] = []
    async for doc in cursor:
        logs.append(
            ActivityLogOut(
                id=str(doc["_id"]),
                customer_id=customer_id,
                action=doc["action"],
                metadata=doc.get("metadata", {}),
                created_at=doc["created_at"],
            )
        )
    return logs


@router.get("/{customer_id}/preferences", response_model=PreferencesOut)
async def get_preferences(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> PreferencesOut:
    await get_customer_or_404(session, customer_id)
    doc = await get_mongo_db().customer_preferences.find_one({"customer_id": str(customer_id)})
    prefs = doc.get("preferences", {}) if doc else {}
    return PreferencesOut(customer_id=customer_id, preferences=prefs)


@router.patch("/{customer_id}/preferences", response_model=PreferencesOut)
async def update_preferences(
    customer_id: UUID,
    payload: PreferencesUpdate,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> PreferencesOut:
    await get_customer_or_404(session, customer_id)
    await get_mongo_db().customer_preferences.update_one(
        {"customer_id": str(customer_id)},
        {"$set": {"preferences": payload.preferences}},
        upsert=True,
    )
    await log_activity(
        customer_id,
        "preferences.updated",
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    return PreferencesOut(customer_id=customer_id, preferences=payload.preferences)


@router.get("/{customer_id}/purchase-history", response_model=list[PurchaseHistoryItem])
async def get_purchase_history(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[PurchaseHistoryItem]:
    await get_customer_or_404(session, customer_id)
    return []


@router.get("/{customer_id}/account-statement", response_model=list[AccountStatementLine])
async def get_account_statement(
    customer_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[AccountStatementLine]:
    await get_customer_or_404(session, customer_id)
    return []
