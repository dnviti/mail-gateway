import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook_event import WebhookEvent

logger = logging.getLogger(__name__)


class IdempotencyGuard:
    """Guards against duplicate processing of Stripe webhook events.

    Uses the webhook_events table to track processed event IDs. Handles
    concurrent duplicate deliveries safely via unique constraint on
    stripe_event_id.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_and_record(
        self, event: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Check if an event has already been processed and record it if not.

        Args:
            event: The parsed Stripe event dictionary.

        Returns:
            A dict with status/message if the event was already processed
            (caller should return this as the response), or None if the
            event is new and should be processed.
        """
        event_id = event.get("id")
        event_type = event.get("type", "unknown")

        if not event_id:
            logger.warning("Webhook event missing 'id' field, skipping idempotency check")
            return None

        stmt = select(WebhookEvent).where(WebhookEvent.stripe_event_id == event_id)
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            logger.info(
                "Duplicate webhook event %s (type=%s, status=%s), skipping",
                event_id,
                event_type,
                existing.status,
            )
            return {
                "status": "skipped",
                "message": f"Event {event_id} already processed",
            }

        return None

    async def record_event(
        self, event: dict[str, Any], status: str = "processed"
    ) -> None:
        """Record a webhook event as processed.

        Args:
            event: The parsed Stripe event dictionary.
            status: The processing status (processed/skipped/failed).
        """
        event_id = event.get("id")
        event_type = event.get("type", "unknown")

        if not event_id:
            return

        webhook_event = WebhookEvent(
            stripe_event_id=event_id,
            event_type=event_type,
            status=status,
        )

        try:
            self.db.add(webhook_event)
            await self.db.commit()
        except IntegrityError:
            # Another concurrent request already recorded this event
            await self.db.rollback()
            logger.info(
                "Event %s was concurrently recorded by another request", event_id
            )
