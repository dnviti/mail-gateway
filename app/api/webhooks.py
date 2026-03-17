import logging
import time

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.deps import get_httpx_client
from app.middleware.idempotency import IdempotencyGuard
from app.models.schemas import WebhookResponse
from app.services.stripe_service import verify_webhook_signature
from app.services.event_router import route_event
from app.services import audit_service

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_ERROR_DETAIL_LENGTH = 500


@router.post("/stripe", response_model=WebhookResponse)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db),
    http_client: httpx.AsyncClient = Depends(get_httpx_client),
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

    event_type = event.get("type", "")
    stripe_event_id = event.get("id", "")

    start_time = time.monotonic()
    status = "processed"
    error_detail = None

    try:
        result = await route_event(event, db, http_client=http_client)

        # Map result status for idempotency and audit
        status_map = {"processed": "processed", "error": "failed"}
        status = status_map.get(result["status"], "skipped")

        if result["status"] == "error":
            error_detail = result.get("message", "Unknown error")

        await guard.record_event(event, status=status)

        return WebhookResponse(status=result["status"], message=result["message"])

    except Exception as exc:
        status = "failed"
        error_detail = f"{type(exc).__name__}: {str(exc)}"[:MAX_ERROR_DETAIL_LENGTH]
        raise

    finally:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        try:
            await audit_service.record_event(
                db=db,
                stripe_event_id=stripe_event_id,
                event_type=event_type,
                customer_id=None,
                payload=event,
                status=status,
                error_detail=error_detail,
                processing_ms=elapsed_ms,
            )
        except Exception:
            logger.exception("Audit logging failed for event %s", stripe_event_id)
