import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.db.database import async_session
from app.models.dead_letter import DeadLetter
from app.utils.pii_redactor import redact_email, redact_payload

logger = logging.getLogger(__name__)

# HTTP status codes considered transient (eligible for retry)
TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass
class RetryConfig:
    """Configuration for retry behaviour with exponential backoff."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    jitter: bool = True


def _is_transient_error(exc: Exception) -> bool:
    """Determine whether an exception represents a transient failure.

    Transient failures are retryable: rate limits (429), server errors (5xx),
    network timeouts, and connection errors.  Permanent failures (4xx auth/
    validation errors) should not be retried.
    """
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, (httpx.ConnectError, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in TRANSIENT_STATUS_CODES
    return False


def _compute_delay(attempt: int, config: RetryConfig) -> float:
    """Compute the backoff delay for a given attempt number.

    Uses exponential backoff capped at *max_delay*, with optional random
    jitter to prevent thundering-herd effects.
    """
    delay = min(config.base_delay * (2 ** attempt), config.max_delay)
    if config.jitter:
        delay = delay * (0.5 + random.random())  # jitter between 50-150% of delay
    return delay


async def _record_dead_letter(
    recipient_email: str,
    template_id: str | None,
    payload: dict | None,
    error_message: str,
    attempts: int,
    first_failed_at: datetime,
) -> None:
    """Persist a permanently-failed email to the dead_letter_emails table."""
    try:
        async with async_session() as session:
            dead_letter = DeadLetter(
                recipient_email=recipient_email,
                template_id=template_id,
                payload=redact_payload(payload),
                error_message=error_message,
                attempts=attempts,
                first_failed_at=first_failed_at,
                last_failed_at=datetime.now(timezone.utc),
                status="pending",
            )
            session.add(dead_letter)
            await session.commit()
            logger.info(
                "Recorded dead letter for %s after %d attempt(s)",
                redact_email(recipient_email),
                attempts,
            )
    except Exception:
        logger.exception("Failed to record dead letter for %s", redact_email(recipient_email))


async def with_retry(
    func,
    *args,
    config: RetryConfig | None = None,
    recipient_email: str = "",
    template_id: str | None = None,
    payload: dict | None = None,
    **kwargs,
):
    """Execute *func* with exponential-backoff retries.

    On transient failures the call is retried up to ``config.max_retries``
    times.  On permanent failure (or after exhausting retries) the email
    details are written to the dead-letter table and ``False`` is returned.

    Parameters
    ----------
    func:
        The async callable to invoke.
    config:
        Retry configuration.  Uses sensible defaults when ``None``.
    recipient_email, template_id, payload:
        Metadata persisted to the dead-letter table on permanent failure.
    """
    if config is None:
        config = RetryConfig()

    first_failed_at: datetime | None = None
    last_exception: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as exc:
            last_exception = exc
            if first_failed_at is None:
                first_failed_at = datetime.now(timezone.utc)

            if not _is_transient_error(exc):
                logger.error(
                    "Permanent failure on attempt %d for %s: %s",
                    attempt + 1,
                    redact_email(recipient_email),
                    exc,
                )
                break

            if attempt < config.max_retries:
                delay = _compute_delay(attempt, config)
                logger.warning(
                    "Transient failure on attempt %d/%d for %s: %s — retrying in %.2fs",
                    attempt + 1,
                    config.max_retries + 1,
                    redact_email(recipient_email),
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "All %d retries exhausted for %s: %s",
                    config.max_retries + 1,
                    redact_email(recipient_email),
                    exc,
                )

    # Permanent failure — record to dead letter table
    actual_attempts = attempt + 1 if last_exception is not None else 1
    error_msg = str(last_exception) if last_exception else "Unknown error"
    # Truncate error message to avoid storing excessive internal details (S-1)
    if len(error_msg) > 1000:
        error_msg = error_msg[:1000] + "... [truncated]"

    await _record_dead_letter(
        recipient_email=recipient_email,
        template_id=template_id,
        payload=payload,
        error_message=error_msg,
        attempts=actual_attempts,
        first_failed_at=first_failed_at or datetime.now(timezone.utc),
    )
    return False
