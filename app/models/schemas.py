from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WebhookResponse(BaseModel):
    status: str
    message: str


class CustomerBase(BaseModel):
    email: str
    name: str | None = None
    stripe_customer_id: str


class CustomerCreate(CustomerBase):
    pass


class AuditLogResponse(BaseModel):
    """Response model for a single audit log entry."""

    id: int
    stripe_event_id: str
    event_type: str
    customer_id: str | None = None
    payload: dict[str, Any] | None = None
    status: str
    error_detail: str | None = None
    processing_ms: int | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Response model for a list of audit log entries."""

    entries: list[AuditLogResponse]
    count: int
