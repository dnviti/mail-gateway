import logging
import time

from fastapi import APIRouter, Header, HTTPException, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.schemas import WebhookResponse
from app.services.stripe_service import verify_webhook_signature, extract_customer_data, is_first_subscription
from app.services.customer_service import get_customer_by_stripe_id
from app.services.brevo_service import send_welcome_email
from app.services import audit_service

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_ERROR_DETAIL_LENGTH = 500


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

    event_type = event.get("type", "")
    stripe_event_id = event.get("id", "")

    start_time = time.monotonic()
    status = "processed"
    error_detail = None
    customer_id = None

    try:
        if event_type == "customer.subscription.created":
            customer_data = extract_customer_data(event)
            stripe_customer_id = customer_data.get("customer_id", "")
            customer_id = stripe_customer_id or None

            if not stripe_customer_id:
                logger.warning("No customer ID in subscription event")
                status = "skipped"
                return WebhookResponse(status="ignored", message="No customer ID")

            if not await is_first_subscription(stripe_customer_id, event):
                status = "skipped"
                return WebhookResponse(status="ignored", message="Not a first subscription")

            customer = await get_customer_by_stripe_id(db, stripe_customer_id)
            if customer is None:
                logger.warning(f"Customer not found in DB: {stripe_customer_id}")
                status = "failed"
                error_detail = f"Customer not found in DB: {stripe_customer_id}"
                return WebhookResponse(status="error", message="Customer not found")

            email_sent = await send_welcome_email(
                to_email=customer.email,
                customer_name=customer.name or "Customer",
            )

            if email_sent:
                status = "processed"
                return WebhookResponse(status="processed", message="Welcome email sent")

            status = "failed"
            error_detail = "Failed to send welcome email"
            return WebhookResponse(status="error", message="Failed to send email")

        status = "skipped"
        return WebhookResponse(status="ignored", message=f"Unhandled event type: {event_type}")

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
                customer_id=customer_id,
                payload=event,
                status=status,
                error_detail=error_detail,
                processing_ms=elapsed_ms,
            )
        except Exception:
            logger.exception("Audit logging failed for event %%s", stripe_event_id)
