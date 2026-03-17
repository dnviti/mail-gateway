import logging
from typing import Any

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook_event import WebhookEvent

logger = logging.getLogger(__name__)


class IdempotencyGuard:
    """Guards against duplicate processing of Stripe webhook events.

    Uses the webhook_events table to track processed event IDs. Handles
    concurrent duplicate deliveries safely via unique constraint on
    stripe_event_id.

    The guard uses an atomic INSERT approach: it inserts a row with status
    'pending' when an event is first seen. If a concurrent request tries
    to insert the same event_id, the unique constraint raises an
    IntegrityError, which is caught and treated as a duplicate. This
    eliminates the race window that exists in a SELECT-then-INSERT pattern.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_and_record(
        self, event: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Atomically claim an event for processing.

        Attempts to INSERT a 'pending' row for the event. If the insert
        succeeds, the caller owns the event and should process it. If it
        fails due to a unique constraint violation, the event was already
        claimed by another request.

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

        webhook_event = WebhookEvent(
            stripe_event_id=event_id,
            event_type=event_type,
            status="pending",
        )

        try:
            self.db.add(webhook_event)
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            logger.info(
                "Duplicate webhook event %s (type=%s), skipping",
                event_id,
                event_type,
            )
            return {
                "status": "skipped",
                "message": f"Event {event_id} already processed",
            }

        return None

    async def record_event(
        self, event: dict[str, Any], status: str = "processed"
    ) -> None:
        """Update the status of a previously claimed event.

        Called after processing to set the final status (processed/skipped/failed).

        Args:
            event: The parsed Stripe event dictionary.
            status: The processing status (processed/skipped/failed).
        """
        event_id = event.get("id")

        if not event_id:
            return

        stmt = (
            update(WebhookEvent)
            .where(WebhookEvent.stripe_event_id == event_id)
            .values(status=status)
        )

        try:
            await self.db.execute(stmt)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            logger.exception(
                "Failed to update status for event %s", event_id
            )
