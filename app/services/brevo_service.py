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


async def send_cancellation_email(to_email: str, customer_name: str) -> bool:
    """Send cancellation confirmation email."""
    html_content = _build_cancellation_html(customer_name)
    return await _send_email(to_email, customer_name, "Subscription Cancelled", html_content)


async def send_payment_failed_email(to_email: str, customer_name: str) -> bool:
    """Send payment failure notification email."""
    html_content = _build_payment_failed_html(customer_name)
    return await _send_email(to_email, customer_name, "Payment Failed — Action Required", html_content)


async def send_renewal_reminder_email(to_email: str, customer_name: str) -> bool:
    """Send subscription renewal reminder email."""
    html_content = _build_renewal_reminder_html(customer_name)
    return await _send_email(to_email, customer_name, "Your Subscription Renewal is Coming Up", html_content)


async def send_plan_change_email(to_email: str, customer_name: str, old_plan: str, new_plan: str) -> bool:
    """Send plan change confirmation email."""
    html_content = _build_plan_change_html(customer_name, old_plan, new_plan)
    return await _send_email(to_email, customer_name, "Your Plan Has Been Changed", html_content)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _send_email(to_email: str, to_name: str, subject: str, html_content: str) -> bool:
    """Send an email via the Brevo API."""
    if not settings.BREVO_API_KEY:
        logger.error("BREVO_API_KEY not configured")
        return False

    payload = {
        "sender": {"name": settings.APP_NAME, "email": f"noreply@{settings.APP_NAME}.com"},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "htmlContent": html_content,
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
                logger.info(f"Email '{subject}' sent to {to_email}")
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


def _build_cancellation_html(customer_name: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #333;">Subscription Cancelled</h1>
    <p>Hi {customer_name},</p>
    <p>Your subscription has been successfully cancelled. We're sorry to see you go.</p>
    <p>You will continue to have access to your account until the end of your current billing period.</p>
    <p>If you change your mind, you can resubscribe at any time from your account settings.</p>
    <p style="color: #666; font-size: 14px;">Best regards,<br>The Team</p>
</body>
</html>"""


def _build_payment_failed_html(customer_name: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #e74c3c;">Payment Failed</h1>
    <p>Hi {customer_name},</p>
    <p>We were unable to process your most recent payment. This could be due to an expired card, insufficient funds, or an issue with your payment method.</p>
    <p>Please update your payment information as soon as possible to avoid any interruption to your service.</p>
    <p>If you believe this is an error, please contact our support team for assistance.</p>
    <p style="color: #666; font-size: 14px;">Best regards,<br>The Team</p>
</body>
</html>"""


def _build_renewal_reminder_html(customer_name: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #333;">Subscription Renewal Reminder</h1>
    <p>Hi {customer_name},</p>
    <p>This is a friendly reminder that your subscription will be renewed soon.</p>
    <p>No action is needed on your part. Your payment method on file will be charged automatically.</p>
    <p>If you'd like to make any changes to your subscription or update your payment details, please visit your account settings before the renewal date.</p>
    <p style="color: #666; font-size: 14px;">Best regards,<br>The Team</p>
</body>
</html>"""


def _build_plan_change_html(customer_name: str, old_plan: str, new_plan: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
    <h1 style="color: #333;">Plan Changed Successfully</h1>
    <p>Hi {customer_name},</p>
    <p>Your subscription plan has been updated.</p>
    <p><strong>Previous plan:</strong> {old_plan}<br>
       <strong>New plan:</strong> {new_plan}</p>
    <p>The changes will be reflected in your next billing cycle. If you have any questions about your new plan, please don't hesitate to contact our support team.</p>
    <p style="color: #666; font-size: 14px;">Best regards,<br>The Team</p>
</body>
</html>"""
