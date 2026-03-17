"""Rate limiting middleware using slowapi.

Configurable via environment variables:
- RATE_LIMIT_ADMIN: Rate limit for admin endpoints (default: "60/minute")
- RATE_LIMIT_WEBHOOK: Rate limit for webhook endpoints (default: "100/minute")
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

# Create limiter keyed by client IP address
limiter = Limiter(key_func=get_remote_address)


def get_admin_rate_limit() -> str:
    """Return the configured rate limit string for admin endpoints."""
    return settings.RATE_LIMIT_ADMIN


def get_webhook_rate_limit() -> str:
    """Return the configured rate limit string for webhook endpoints."""
    return settings.RATE_LIMIT_WEBHOOK
