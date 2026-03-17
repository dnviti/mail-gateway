import logging

import stripe

from app.config import settings

logger = logging.getLogger(__name__)


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict | None:
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
        return event
    except stripe.SignatureVerificationError:
        logger.error("Invalid Stripe webhook signature")
        return None
    except ValueError:
        logger.error("Invalid Stripe webhook payload")
        return None


def extract_customer_data(event: dict) -> dict:
    data_object = event.get("data", {}).get("object", {})
    return {
        "customer_id": data_object.get("customer", ""),
        "subscription_id": data_object.get("id", ""),
        "status": data_object.get("status", ""),
        "plan_id": data_object.get("plan", {}).get("id", "") if data_object.get("plan") else "",
    }


async def is_first_subscription(customer_id: str, event: dict) -> bool:
    data_object = event.get("data", {}).get("object", {})
    # A first subscription is indicated by the subscription being newly created
    # and the customer having no previous subscriptions in the event metadata.
    # For a more robust check, query Stripe API for customer's subscription count.
    previous_attributes = event.get("data", {}).get("previous_attributes", {})
    if previous_attributes:
        return False
    status = data_object.get("status", "")
    return status in ("active", "trialing")
