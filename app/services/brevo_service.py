import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


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

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(BREVO_API_URL, json=payload, headers=headers, timeout=30.0)
            if response.status_code in (200, 201):
                logger.info(f"Welcome email sent to {to_email}")
                return True
            logger.error(f"Brevo API error: {response.status_code} - {response.text}")
            return False
    except httpx.HTTPError as e:
        logger.error(f"Failed to send email via Brevo: {e}")
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
