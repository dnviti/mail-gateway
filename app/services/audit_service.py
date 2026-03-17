import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.utils.pii_redactor import redact_payload

logger = logging.getLogger(__name__)


async def record_event(
    db: AsyncSession,
    stripe_event_id: str,
    event_type: str,
    customer_id: str | None,
    payload: dict[str, Any] | None,
    status: str,
    error_detail: str | None = None,
    processing_ms: int | None = None,
) -> AuditLog | None:
    """Record a webhook event in the audit log.

    Wrapped in try/except — audit failures must never block email delivery.
    """
    try:
        entry = AuditLog(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            customer_id=customer_id,
            payload=redact_payload(payload),
            status=status,
            error_detail=error_detail,
            processing_ms=processing_ms,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return entry
    except Exception:
        logger.exception("Failed to record audit log entry for event %s", stripe_event_id)
        await db.rollback()
        return None


async def query_audit_log(
    db: AsyncSession,
    event_type: str | None = None,
    customer_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditLog]:
    """Query audit log entries with optional filters."""
    query = select(AuditLog)

    if event_type is not None:
        query = query.where(AuditLog.event_type == event_type)
    if customer_id is not None:
        query = query.where(AuditLog.customer_id == customer_id)
    if date_from is not None:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        query = query.where(AuditLog.created_at <= date_to)
    if status is not None:
        query = query.where(AuditLog.status == status)

    query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return list(result.scalars().all())
