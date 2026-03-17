from datetime import datetime
from enum import Enum

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.middleware.rate_limiter import limiter, get_admin_rate_limit
from app.models.schemas import AuditLogListResponse, AuditLogResponse
from app.services.audit_service import query_audit_log

router = APIRouter()


class AuditStatus(str, Enum):
    processed = "processed"
    skipped = "skipped"
    failed = "failed"


async def verify_admin_api_key(
    x_api_key: str = Header(alias="X-API-Key"),
) -> str:
    if not settings.ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="Admin endpoint not configured")
    if x_api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key


@router.get("/audit-log", response_model=AuditLogListResponse)
@limiter.limit(get_admin_rate_limit)
async def get_audit_log(
    request: Request,
    event_type: str | None = Query(default=None, description="Filter by event type"),
    customer_id: str | None = Query(default=None, description="Filter by customer ID"),
    date_from: datetime | None = Query(default=None, description="Filter from date (ISO 8601)"),
    date_to: datetime | None = Query(default=None, description="Filter to date (ISO 8601)"),
    status: AuditStatus | None = Query(default=None, description="Filter by status (processed/skipped/failed)"),
    limit: int = Query(default=50, ge=1, le=200, description="Max entries to return"),
    offset: int = Query(default=0, ge=0, description="Number of entries to skip"),
    db: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_admin_api_key),
) -> AuditLogListResponse:
    entries = await query_audit_log(
        db=db,
        event_type=event_type,
        customer_id=customer_id,
        date_from=date_from,
        date_to=date_to,
        status=status.value if status else None,
        limit=limit,
        offset=offset,
    )
    items = [
        AuditLogResponse(
            id=entry.id,
            stripe_event_id=entry.stripe_event_id,
            event_type=entry.event_type,
            customer_id=entry.customer_id,
            payload=entry.payload,
            status=entry.status,
            error_detail=entry.error_detail,
            processing_ms=entry.processing_ms,
            created_at=entry.created_at.isoformat() if entry.created_at else None,
        )
        for entry in entries
    ]
    return AuditLogListResponse(entries=items, count=len(items))
