import logging

from fastapi import APIRouter, Header, HTTPException, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.middleware.idempotency import IdempotencyGuard
from app.models.schemas import WebhookResponse
from app.services.stripe_service import verify_webhook_signature
from app.services.event_router import route_event

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/stripe", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
):
    payload = await request.body()

    event = verify_webhook_signature(payload, stripe_signature)
    if event is None:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # Idempotency check: skip if this event was already processed
    guard = IdempotencyGuard(db)
    duplicate = await guard.check_and_record(event)
    if duplicate is not None:
        return WebhookResponse(**duplicate)

    result = await route_event(event, db)

    # Record event outcome for idempotency
    status_map = {"processed": "processed", "error": "failed"}
    await guard.record_event(event, status=status_map.get(result["status"], "skipped"))

    return WebhookResponse(status=result["status"], message=result["message"])
