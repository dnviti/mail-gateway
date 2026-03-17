---
title: Configuration
description: Environment variables, config files, and feature flags for the mail-gateway microservice
generated-by: ctdf-docs
generated-at: 2026-03-17T00:00:00Z
source-files:
  - app/config.py
  - .env.example
---

## How Configuration Works

All configuration is managed through environment variables loaded by pydantic-settings (`app/config.py`). The `Settings` class reads from a `.env` file (UTF-8 encoded) at the project root and falls back to environment variables. No other config files are used.

The `settings` singleton is instantiated at module load time and imported throughout the codebase as `from app.config import settings`.

## Environment Variables

### Required

These must be set for the application to function correctly:

| Variable | Type | Example | Description |
|----------|------|---------|-------------|
| `STRIPE_WEBHOOK_SECRET` | `str` | `whsec_abc123...` | Stripe webhook endpoint signing secret. Used to verify webhook signatures. Obtain from the Stripe Dashboard under Webhooks. |
| `BREVO_API_KEY` | `str` | `xkeysib-abc123...` | Brevo (formerly Sendinblue) SMTP API key. Used to send transactional emails. Obtain from the Brevo account settings. |
| `DATABASE_URL` | `str` | `postgresql+asyncpg://user:pass@localhost:5432/mail_gateway` | Async PostgreSQL connection string. Must use the `asyncpg` driver scheme. |

### Application

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APP_NAME` | `str` | `mail-gateway` | Application display name. Used as the email sender name and in the health check response. |
| `DEBUG` | `bool` | `false` | Enables SQLAlchemy query echo for database debugging. |
| `PORT` | `int` | `8000` | Default server port (used by convention; uvicorn must be started with `--port` explicitly). |

### Authentication

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `ADMIN_API_KEY` | `str` | `""` (empty) | API key for the admin audit-log endpoint. When empty, the admin endpoint returns 503 (not configured). Clients pass this via the `X-API-Key` header. |

### Email

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SENDER_EMAIL` | `str` | `""` (derived) | Override for the sender email address. When empty, derived as `noreply@{APP_NAME}.com`. Validated against RFC 5322 simplified pattern at access time. |

### Rate Limiting

| Variable | Type | Default | Validation |
|----------|------|---------|------------|
| `RATE_LIMIT_ADMIN` | `str` | `60/minute` | Must match `<number>/<second\|minute\|hour\|day>` |
| `RATE_LIMIT_WEBHOOK` | `str` | `100/minute` | Must match `<number>/<second\|minute\|hour\|day>` |

Rate limiting is IP-based via slowapi. Invalid format raises a `ValueError` at startup.

### PII Redaction (GDPR)

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PII_REDACTION_ENABLED` | `bool` | `true` | Master switch for PII redaction. When enabled, emails are masked in logs (`d***@example.com`), names are masked (`D*** V***`), and webhook payloads stored in audit logs are scrubbed of sensitive fields. Disable only in development. |
| `PII_HASH_SALT` | `str` | `""` (empty) | Salt for SHA-256 correlation hashes attached to redacted payloads. Set a unique, secret value per deployment to prevent rainbow-table reversal. |

### Retention / TTL

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WEBHOOK_EVENTS_TTL_DAYS` | `int` | `30` | Days after which `webhook_events` rows are deleted. Minimum enforced: 1 day. |
| `DEAD_LETTER_TTL_DAYS` | `int` | `90` | Days after which `dead_letter_emails` rows are deleted. Minimum enforced: 1 day. |
| `RETENTION_CLEANUP_INTERVAL_HOURS` | `int` | `24` | Hours between background retention cleanup cycles. |
| `RETENTION_BATCH_SIZE` | `int` | `1000` | Maximum rows deleted per batch during cleanup to avoid long-running transactions. |

## Configuration Flow

```mermaid
flowchart LR
    ENV[".env file"] --> PS["pydantic-settings\n(Settings class)"]
    OS["OS Environment\nVariables"] --> PS
    PS --> S["settings singleton\n(app/config.py)"]
    S --> APP["FastAPI app"]
    S --> DB["Database engine"]
    S --> BS["Brevo service"]
    S --> RL["Rate limiter"]
    S --> PII["PII redactor"]
    S --> RET["Retention service"]
```

## Validation

The `Settings` class performs validation at startup:

| Field | Validation | Error on failure |
|-------|-----------|------------------|
| `RATE_LIMIT_ADMIN` | Regex: `^\d+/(second\|minute\|hour\|day)$` | `ValueError` with format hint |
| `RATE_LIMIT_WEBHOOK` | Regex: `^\d+/(second\|minute\|hour\|day)$` | `ValueError` with format hint |
| `sender_email` (property) | RFC 5322 simplified regex on access | `ValueError` with message |

## .env.example

The repository includes `.env.example` as a template:

```env
STRIPE_WEBHOOK_SECRET=whsec_your_stripe_webhook_secret
BREVO_API_KEY=your_brevo_api_key
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mail_gateway
APP_NAME=mail-gateway
DEBUG=false
PORT=8000
```

Copy this file to `.env` and replace placeholder values with real credentials. Never commit `.env` to version control.
