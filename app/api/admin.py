from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.audit_service import query_audit_log

router = APIRouter()


@router.get("/audit-log")
async def get_audit_log(
    event_type: str | None = Query(default=None, description="Filter by event type"),
    customer_id: str | None = Query(default=None, description="Filter by customer ID"),
    date_from: datetime | None = Query(default=None, description="Filter from date (ISO 8601)"),
    date_to: datetime | None = Query(default=None, description="Filter to date (ISO 8601)"),
    status: str | None = Query(default=None, description="Filter by status (processed/skipped/failed)"),
    limit: int = Query(default=50, ge=1, le=200, description="Max entries to return"),
    offset: int = Query(default=0, ge=0, description="Number of entries to skip"),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    entries = await query_audit_log(
        db=db,
        event_type=event_type,
        customer_id=customer_id,
        date_from=date_from,
        date_to=date_to,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [
        {
            "id": entry.id,
            "stripe_event_id": entry.stripe_event_id,
            "event_type": entry.event_type,
            "customer_id": entry.customer_id,
            "payload": entry.payload,
            "status": entry.status,
            "error_detail": entry.error_detail,
            "processing_ms": entry.processing_ms,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
        }
        for entry in entries
    ]
