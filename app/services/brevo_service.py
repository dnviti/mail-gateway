import logging

import httpx

from app.config import settings
from app.services.retry_service import RetryConfig, with_retry

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

# Retry configuration for Brevo API calls
_retry_config = RetryConfig(max_retries=3, base_delay=1.0, max_delay=30.0, jitter=True)


async def _send_email_request(payload: dict, headers: dict, client: httpx.AsyncClient | None = None) -> bool:
    """Execute a single Brevo API request.

    Raises on transient errors so the retry wrapper can handle them.
    Permanent errors (4xx except 429) also raise but are classified
    as non-transient by the retry service.
    """
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient()
    try:
        response = await client.post(
            BREVO_API_URL, json=payload, headers=headers, timeout=30.0
        )
        if response.status_code in (200, 201):
            return True
        # Raise an HTTPStatusError so retry_service can inspect the status code
        response.raise_for_status()
    finally:
        if owns_client:
            await client.aclose()
    return False  # pragma: no cover


async def send_welcome_email(to_email: str, customer_name: str) -> bool:
    if not settings.BREVO_API_KEY:
        logger.error("BREVO_API_KEY not configured")
        return False

    payload = {
        "sender": {"name": settings.APP_NAME, "email": f"noreply@{settings.APP_NAME}.com"},
        "to": [{"email": to_email, "name": customer_name}],
        "subject": "Welcome to our service!",
        "htmlContent": _build_welcome_html(customer_name),
    }

    headers = {
        "api-key": settings.BREVO_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    logger.info("Sending welcome email to %s (with retry)", to_email)
    async with httpx.AsyncClient() as client:
        result = await with_retry(
            _send_email_request,
            payload,
            headers,
            client,
            config=_retry_config,
            recipient_email=to_email,
            template_id="welcome",
            payload=payload,
        )

    if result is True:
        logger.info("Welcome email sent to %s", to_email)
        return True

    logger.error("Welcome email delivery failed permanently for %s", to_email)
    return False


def _build_welcome_html(customer_name: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #333;">Welcome, {customer_name}!</h1>
    <p>Thank you for subscribing to our service. We're excited to have you on board.</p>
    <p>If you have any questions, feel free to reach out to our support team.</p>
    <p style="color: #666; font-size: 14px;">Best regards,<br>The Team</p>
</body>
</html>"""
