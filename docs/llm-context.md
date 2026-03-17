---
title: LLM Context
description: Consolidated single-file reference for the mail-gateway microservice, optimized for LLM and bot consumption
generated-by: ctdf-docs
generated-at: 2026-03-17T00:00:00Z
source-files:
  - app/main.py
  - app/config.py
  - app/deps.py
  - app/api/webhooks.py
  - app/api/admin.py
  - app/db/database.py
  - app/middleware/idempotency.py
  - app/middleware/rate_limiter.py
  - app/services/event_router.py
  - app/services/stripe_service.py
  - app/services/brevo_service.py
  - app/services/customer_service.py
  - app/services/audit_service.py
  - app/services/retry_service.py
  - app/services/retention_service.py
  - app/utils/pii_redactor.py
  - app/models/customer.py
  - app/models/webhook_event.py
  - app/models/audit_log.py
  - app/models/dead_letter.py
  - app/models/schemas.py
  - pyproject.toml
---

## Project Summary

**mail-gateway** (v0.0.1) is a Python FastAPI microservice that bridges Stripe payment events with transactional email delivery via Brevo. It receives Stripe webhooks at `POST /webhooks/stripe`, verifies signatures, deduplicates events, routes them to type-specific handlers, and sends emails with retry support. Failed deliveries go to a dead-letter table. All payloads are PII-redacted before audit storage. A background task handles data retention.

---

## Stack

- Python >= 3.11, FastAPI >= 0.109.0, Uvicorn >= 0.27.0
- PostgreSQL via SQLAlchemy async (asyncpg >= 0.29.0)
- Stripe Python SDK >= 8.0.0
- Brevo SMTP API via httpx >= 0.27.0
- pydantic-settings >= 2.1.0, slowapi >= 0.1.9
- Testing: pytest >= 8.0.0, pytest-asyncio >= 0.23.0
- Linting: ruff >= 0.9.0

---

## Architecture

Stripe -> POST /webhooks/stripe -> Rate Limiter -> Signature Verification -> Idempotency Guard -> Event Router -> Handler -> Brevo Service (with Retry) -> Brevo API. Failures go to dead_letter_emails table. All events are audit-logged with PII redaction.

---

## Endpoints

### POST /webhooks/stripe
- Auth: Stripe-Signature header (verified with STRIPE_WEBHOOK_SECRET)
- Rate limit: RATE_LIMIT_WEBHOOK (default 100/minute)
- Response: `{"status": "<processed|skipped|ignored|rejected|error>", "message": "..."}`
- Handled events: customer.subscription.created (welcome email, first sub only), customer.subscription.deleted (cancellation), customer.subscription.updated (plan change), invoice.payment_failed (payment failure), invoice.upcoming (renewal reminder)

### GET /admin/audit-log
- Auth: X-API-Key header (must match ADMIN_API_KEY)
- Rate limit: RATE_LIMIT_ADMIN (default 60/minute)
- Query params: event_type, customer_id, date_from, date_to, status (processed|skipped|failed), limit (1-200), offset
- Response: `{"entries": [...], "count": N}`
- Returns 503 if ADMIN_API_KEY is not configured

### GET /health
- No auth
- Response: `{"status": "healthy", "service": "<APP_NAME>"}`

---

## Database Tables

- **customers**: id, email, name, stripe_customer_id (unique), created_at, updated_at
- **webhook_events**: id, stripe_event_id (unique), event_type, status, processed_at — used for idempotency
- **webhook_audit_log**: id, stripe_event_id, event_type, customer_id, payload (JSON, PII-redacted), status, error_detail, processing_ms, created_at
- **dead_letter_emails**: id, recipient_email, template_id, payload (JSON, PII-redacted), error_message, attempts, first_failed_at, last_failed_at, status

Tables are auto-created on startup via SQLAlchemy metadata.create_all().

---

## Configuration (Environment Variables)

Required: STRIPE_WEBHOOK_SECRET, BREVO_API_KEY, DATABASE_URL (postgresql+asyncpg://...)

Optional: APP_NAME (default: mail-gateway), DEBUG (default: false), PORT (default: 8000), ADMIN_API_KEY, SENDER_EMAIL, PII_REDACTION_ENABLED (default: true), PII_HASH_SALT, RATE_LIMIT_ADMIN (default: 60/minute), RATE_LIMIT_WEBHOOK (default: 100/minute), WEBHOOK_EVENTS_TTL_DAYS (default: 30), DEAD_LETTER_TTL_DAYS (default: 90), RETENTION_CLEANUP_INTERVAL_HOURS (default: 24), RETENTION_BATCH_SIZE (default: 1000)

Loaded from .env file via pydantic-settings.

---

## Key Files

- `app/main.py` — FastAPI app, lifespan (DB init, httpx client, retention task), health endpoint, rate limit handler
- `app/config.py` — Settings class (pydantic-settings), validation, sender_email property
- `app/api/webhooks.py` — POST /webhooks/stripe endpoint, orchestrates verification/idempotency/routing/audit
- `app/api/admin.py` — GET /admin/audit-log, API key auth, query filters
- `app/db/database.py` — SQLAlchemy async engine, session factory, init_db, close_db
- `app/middleware/idempotency.py` — IdempotencyGuard: atomic INSERT dedup, event ID format validation
- `app/middleware/rate_limiter.py` — slowapi Limiter, IP-based, configurable per endpoint
- `app/services/event_router.py` — Registry-based dispatcher, 5 handlers registered
- `app/services/stripe_service.py` — Webhook signature verification, customer data extraction
- `app/services/brevo_service.py` — Email sending via Brevo API, inline HTML templates, retry wrapper
- `app/services/customer_service.py` — get_customer_by_stripe_id (SELECT by stripe_customer_id)
- `app/services/audit_service.py` — record_event (INSERT with PII redaction), query_audit_log
- `app/services/retry_service.py` — Exponential backoff, transient/permanent classification, dead-letter persistence
- `app/services/retention_service.py` — Background TTL cleanup loop, batch deletion
- `app/utils/pii_redactor.py` — redact_email, redact_name, redact_payload, pii_hash, redact_error_message
- `app/models/schemas.py` — Pydantic models: WebhookResponse, CustomerBase, AuditLogResponse, AuditLogListResponse
- `app/models/customer.py` — Customer SQLAlchemy model + DeclarativeBase
- `app/models/webhook_event.py` — WebhookEvent model
- `app/models/audit_log.py` — AuditLog model
- `app/models/dead_letter.py` — DeadLetter model

---

## Commands

```bash
pip install -r requirements.txt          # Install production deps
pip install -r requirements-dev.txt      # Install dev deps
uvicorn app.main:app --reload --port 8000  # Dev server
pytest                                    # Run tests
ruff check .                              # Lint
```

---

## CI/CD

- **CI** (ci.yml): PR to main/develop/staging — lint (ruff), test (pytest), verify syntax
- **Staging** (staging-merge.yml): Push to staging — validate + Docker build (latest tag)
- **Release** (release.yml): Push v* tag — test + GitHub Release + Docker build (stable + versioned)
- **Security** (security.yml): Dependency review on PRs, TruffleHog secret scanning weekly
- **Issue Triage** (issue-triage.yml): Auto-label new issues
- **Status Guard** (status-guard.yml): Enforce status label state machine
