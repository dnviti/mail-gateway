"""Retention / TTL cleanup service for webhook_events and dead_letter_emails tables.

Runs as an asyncio background task, periodically deleting rows older than the
configured TTL to prevent unbounded table growth.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.config import settings
from app.db.database import async_session
from app.models.dead_letter import DeadLetter
from app.models.webhook_event import WebhookEvent

logger = logging.getLogger(__name__)


async def cleanup_webhook_events(batch_size: int | None = None) -> int:
    """Delete webhook_events rows older than WEBHOOK_EVENTS_TTL_DAYS.

    Deletes in batches to avoid long-running transactions and excessive lock
    contention.  Returns the total number of rows deleted.
    """
    ttl_days = settings.WEBHOOK_EVENTS_TTL_DAYS
    batch = batch_size or settings.RETENTION_BATCH_SIZE
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)

    total_deleted = 0

    async with async_session() as session:
        while True:
            # Find IDs of rows past the cutoff in a bounded batch
            subq = (
                select(WebhookEvent.id)
                .where(WebhookEvent.processed_at < cutoff)
                .limit(batch)
            )
            result = await session.execute(subq)
            ids = [row[0] for row in result.all()]

            if not ids:
                break

            stmt = delete(WebhookEvent).where(WebhookEvent.id.in_(ids))
            delete_result = await session.execute(stmt)
            await session.commit()

            deleted_count = delete_result.rowcount  # type: ignore[union-attr]
            total_deleted += deleted_count
            logger.info(
                "Retention: deleted %d webhook_events (batch), total so far: %d",
                deleted_count,
                total_deleted,
            )

            # If the batch was not full, there are no more rows to delete
            if len(ids) < batch:
                break

    if total_deleted > 0:
        logger.info(
            "Retention: finished webhook_events cleanup — %d rows deleted (TTL=%d days)",
            total_deleted,
            ttl_days,
        )
    else:
        logger.debug("Retention: no webhook_events rows older than %d days", ttl_days)

    return total_deleted


async def cleanup_dead_letters(batch_size: int | None = None) -> int:
    """Delete dead_letter_emails rows older than DEAD_LETTER_TTL_DAYS.

    Deletes in batches to avoid long-running transactions and excessive lock
    contention.  Returns the total number of rows deleted.
    """
    ttl_days = settings.DEAD_LETTER_TTL_DAYS
    batch = batch_size or settings.RETENTION_BATCH_SIZE
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)

    total_deleted = 0

    async with async_session() as session:
        while True:
            subq = (
                select(DeadLetter.id)
                .where(DeadLetter.first_failed_at < cutoff)
                .limit(batch)
            )
            result = await session.execute(subq)
            ids = [row[0] for row in result.all()]

            if not ids:
                break

            stmt = delete(DeadLetter).where(DeadLetter.id.in_(ids))
            delete_result = await session.execute(stmt)
            await session.commit()

            deleted_count = delete_result.rowcount  # type: ignore[union-attr]
            total_deleted += deleted_count
            logger.info(
                "Retention: deleted %d dead_letter_emails (batch), total so far: %d",
                deleted_count,
                total_deleted,
            )

            if len(ids) < batch:
                break

    if total_deleted > 0:
        logger.info(
            "Retention: finished dead_letter_emails cleanup — %d rows deleted (TTL=%d days)",
            total_deleted,
            ttl_days,
        )
    else:
        logger.debug(
            "Retention: no dead_letter_emails rows older than %d days", ttl_days
        )

    return total_deleted


async def run_cleanup() -> dict[str, int]:
    """Execute a single cleanup cycle for all managed tables.

    Returns a summary dict with the count of deleted rows per table.
    """
    logger.info("Retention: starting cleanup cycle")
    results: dict[str, int] = {}

    try:
        results["webhook_events"] = await cleanup_webhook_events()
    except Exception:
        logger.exception("Retention: error cleaning up webhook_events")
        results["webhook_events"] = -1

    try:
        results["dead_letter_emails"] = await cleanup_dead_letters()
    except Exception:
        logger.exception("Retention: error cleaning up dead_letter_emails")
        results["dead_letter_emails"] = -1

    logger.info("Retention: cleanup cycle complete — %s", results)
    return results


async def retention_loop() -> None:
    """Long-running background loop that triggers periodic cleanup.

    Designed to be launched via ``asyncio.create_task()`` during application
    startup.  Runs indefinitely until the task is cancelled.
    """
    interval_seconds = settings.RETENTION_CLEANUP_INTERVAL_HOURS * 3600
    logger.info(
        "Retention: background loop started (interval=%dh, webhook_events TTL=%dd, "
        "dead_letter TTL=%dd)",
        settings.RETENTION_CLEANUP_INTERVAL_HOURS,
        settings.WEBHOOK_EVENTS_TTL_DAYS,
        settings.DEAD_LETTER_TTL_DAYS,
    )

    while True:
        try:
            await run_cleanup()
        except Exception:
            logger.exception("Retention: unexpected error in cleanup cycle")

        await asyncio.sleep(interval_seconds)
