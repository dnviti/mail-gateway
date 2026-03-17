import logging
from typing import Callable, Awaitable

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.stripe_service import extract_customer_data, is_first_subscription
from app.services.customer_service import get_customer_by_stripe_id
from app.services.brevo_service import (
    send_welcome_email,
    send_cancellation_email,
    send_payment_failed_email,
    send_renewal_reminder_email,
    send_plan_change_email,
)

logger = logging.getLogger(__name__)

# Registry mapping Stripe event types to async handler functions
_handler_registry: dict[str, Callable[..., Awaitable[dict]]] = {}


def register_handler(event_type: str, handler: Callable[..., Awaitable[dict]]) -> None:
    """Register an async handler for a Stripe event type."""
    _handler_registry[event_type] = handler
    logger.debug("Registered handler for event type: %s", event_type)


async def route_event(event: dict, db: AsyncSession) -> dict:
    """Dispatch a Stripe event to its registered handler."""
    event_type = event.get("type", "")
    handler = _handler_registry.get(event_type)

    if handler is None:
        logger.info("No handler registered for event type: %s", event_type)
        return {"status": "ignored", "message": f"Unhandled event type: {event_type}"}

    return await handler(event, db)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def _handle_subscription_created(event: dict, db: AsyncSession) -> dict:
    """Handle customer.subscription.created — send welcome email on first subscription."""
    customer_data = extract_customer_data(event)
    stripe_customer_id = customer_data.get("customer_id", "")

    if not stripe_customer_id:
        logger.warning("No customer ID in subscription event")
        return {"status": "ignored", "message": "No customer ID"}

    if not await is_first_subscription(stripe_customer_id, event):
        return {"status": "ignored", "message": "Not a first subscription"}

    customer = await get_customer_by_stripe_id(db, stripe_customer_id)
    if customer is None:
        logger.warning("Customer not found in DB: %s", stripe_customer_id)
        return {"status": "error", "message": "Customer not found"}

    email_sent = await send_welcome_email(
        to_email=customer.email,
        customer_name=customer.name or "Customer",
    )

    if email_sent:
        return {"status": "processed", "message": "Welcome email sent"}
    return {"status": "error", "message": "Failed to send email"}


async def _handle_subscription_deleted(event: dict, db: AsyncSession) -> dict:
    """Handle customer.subscription.deleted — send cancellation confirmation."""
    customer_data = extract_customer_data(event)
    stripe_customer_id = customer_data.get("customer_id", "")

    if not stripe_customer_id:
        logger.warning("No customer ID in subscription deleted event")
        return {"status": "ignored", "message": "No customer ID"}

    customer = await get_customer_by_stripe_id(db, stripe_customer_id)
    if customer is None:
        logger.warning("Customer not found in DB: %s", stripe_customer_id)
        return {"status": "error", "message": "Customer not found"}

    email_sent = await send_cancellation_email(
        to_email=customer.email,
        customer_name=customer.name or "Customer",
    )

    if email_sent:
        return {"status": "processed", "message": "Cancellation email sent"}
    return {"status": "error", "message": "Failed to send cancellation email"}


async def _handle_payment_failed(event: dict, db: AsyncSession) -> dict:
    """Handle invoice.payment_failed — notify customer of payment failure."""
    data_object = event.get("data", {}).get("object", {})
    stripe_customer_id = data_object.get("customer", "")

    if not stripe_customer_id:
        logger.warning("No customer ID in payment failed event")
        return {"status": "ignored", "message": "No customer ID"}

    customer = await get_customer_by_stripe_id(db, stripe_customer_id)
    if customer is None:
        logger.warning("Customer not found in DB: %s", stripe_customer_id)
        return {"status": "error", "message": "Customer not found"}

    email_sent = await send_payment_failed_email(
        to_email=customer.email,
        customer_name=customer.name or "Customer",
    )

    if email_sent:
        return {"status": "processed", "message": "Payment failed email sent"}
    return {"status": "error", "message": "Failed to send payment failed email"}


async def _handle_invoice_upcoming(event: dict, db: AsyncSession) -> dict:
    """Handle invoice.upcoming — send renewal reminder."""
    data_object = event.get("data", {}).get("object", {})
    stripe_customer_id = data_object.get("customer", "")

    if not stripe_customer_id:
        logger.warning("No customer ID in invoice upcoming event")
        return {"status": "ignored", "message": "No customer ID"}

    customer = await get_customer_by_stripe_id(db, stripe_customer_id)
    if customer is None:
        logger.warning("Customer not found in DB: %s", stripe_customer_id)
        return {"status": "error", "message": "Customer not found"}

    email_sent = await send_renewal_reminder_email(
        to_email=customer.email,
        customer_name=customer.name or "Customer",
    )

    if email_sent:
        return {"status": "processed", "message": "Renewal reminder email sent"}
    return {"status": "error", "message": "Failed to send renewal reminder email"}


async def _handle_subscription_updated(event: dict, db: AsyncSession) -> dict:
    """Handle customer.subscription.updated — send plan change confirmation."""
    customer_data = extract_customer_data(event)
    stripe_customer_id = customer_data.get("customer_id", "")

    if not stripe_customer_id:
        logger.warning("No customer ID in subscription updated event")
        return {"status": "ignored", "message": "No customer ID"}

    # Detect plan change from previous_attributes
    previous_attributes = event.get("data", {}).get("previous_attributes", {})
    if "plan" not in previous_attributes and "items" not in previous_attributes:
        return {"status": "ignored", "message": "Not a plan change"}

    customer = await get_customer_by_stripe_id(db, stripe_customer_id)
    if customer is None:
        logger.warning("Customer not found in DB: %s", stripe_customer_id)
        return {"status": "error", "message": "Customer not found"}

    data_object = event.get("data", {}).get("object", {})
    new_plan = data_object.get("plan", {}).get("id", "unknown") if data_object.get("plan") else "unknown"
    old_plan = previous_attributes.get("plan", {}).get("id", "unknown") if previous_attributes.get("plan") else "unknown"

    email_sent = await send_plan_change_email(
        to_email=customer.email,
        customer_name=customer.name or "Customer",
        old_plan=old_plan,
        new_plan=new_plan,
    )

    if email_sent:
        return {"status": "processed", "message": "Plan change email sent"}
    return {"status": "error", "message": "Failed to send plan change email"}


# ---------------------------------------------------------------------------
# Register all handlers
# ---------------------------------------------------------------------------

register_handler("customer.subscription.created", _handle_subscription_created)
register_handler("customer.subscription.deleted", _handle_subscription_deleted)
register_handler("invoice.payment_failed", _handle_payment_failed)
register_handler("invoice.upcoming", _handle_invoice_upcoming)
register_handler("customer.subscription.updated", _handle_subscription_updated)
