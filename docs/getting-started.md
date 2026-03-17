---
title: Getting Started
description: Installation, prerequisites, and first run instructions for the mail-gateway microservice
generated-by: ctdf-docs
generated-at: 2026-03-17T00:00:00Z
source-files:
  - pyproject.toml
  - requirements.txt
  - requirements-dev.txt
  - .env.example
  - app/main.py
  - app/config.py
  - app/db/database.py
---

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | >= 3.11 | Runtime |
| PostgreSQL | >= 14 | Primary database (async via asyncpg) |
| Stripe account | — | Webhook source; provides `STRIPE_WEBHOOK_SECRET` |
| Brevo account | — | Email delivery; provides `BREVO_API_KEY` |

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/dnviti/mail-gateway.git
cd mail-gateway
```

### 2. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
```

### 3. Install Dependencies

**Production:**

```bash
pip install -r requirements.txt
```

**Development (includes pytest, ruff):**

```bash
pip install -r requirements-dev.txt
```

### 4. Configure Environment

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Required variables:

| Variable | Example | Description |
|----------|---------|-------------|
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` | Stripe webhook signing secret |
| `BREVO_API_KEY` | `xkeysib-...` | Brevo SMTP API key |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@localhost:5432/mail_gateway` | Async PostgreSQL connection string |

Optional variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `mail-gateway` | Application name (used in email sender) |
| `DEBUG` | `false` | Enable SQLAlchemy echo and debug logging |
| `PORT` | `8000` | Server listen port |
| `ADMIN_API_KEY` | `""` | API key for admin endpoints; admin is disabled when empty |
| `SENDER_EMAIL` | `noreply@{APP_NAME}.com` | Override sender email address |
| `PII_REDACTION_ENABLED` | `true` | Enable GDPR-compliant PII masking |
| `PII_HASH_SALT` | `""` | Salt for PII correlation hashes |
| `RATE_LIMIT_ADMIN` | `60/minute` | Rate limit for admin endpoints |
| `RATE_LIMIT_WEBHOOK` | `100/minute` | Rate limit for webhook endpoints |
| `WEBHOOK_EVENTS_TTL_DAYS` | `30` | Days before webhook events are purged |
| `DEAD_LETTER_TTL_DAYS` | `90` | Days before dead letters are purged |
| `RETENTION_CLEANUP_INTERVAL_HOURS` | `24` | Hours between retention cleanup cycles |
| `RETENTION_BATCH_SIZE` | `1000` | Rows per cleanup batch |

### 5. Set Up the Database

Create the PostgreSQL database:

```bash
createdb mail_gateway
```

Tables are created automatically on application startup via SQLAlchemy's `Base.metadata.create_all()` in `app/db/database.py:init_db()`.

### 6. Run the Application

```bash
uvicorn app.main:app --reload --port 8000
```

### 7. Verify

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "healthy", "service": "mail-gateway"}
```

## First Run Checklist

```mermaid
flowchart LR
    A["Clone repo"] --> B["Create venv"]
    B --> C["Install deps"]
    C --> D["Configure .env"]
    D --> E["Create database"]
    E --> F["Start uvicorn"]
    F --> G["GET /health"]
    G --> H["Configure Stripe\nwebhook URL"]
```

1. Install Python 3.11+ and PostgreSQL
2. Clone and install dependencies
3. Configure `.env` with Stripe, Brevo, and database credentials
4. Create the PostgreSQL database
5. Start the dev server with `uvicorn app.main:app --reload --port 8000`
6. Verify health at `http://localhost:8000/health`
7. Configure Stripe to send webhooks to `https://your-domain/webhooks/stripe`

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Web framework | FastAPI | >= 0.109.0 |
| ASGI server | Uvicorn | >= 0.27.0 |
| ORM | SQLAlchemy (async) | >= 2.0.25 |
| DB driver | asyncpg | >= 0.29.0 |
| HTTP client | httpx | >= 0.27.0 |
| Payment | stripe (Python SDK) | >= 8.0.0 |
| Settings | pydantic-settings | >= 2.1.0 |
| Rate limiting | slowapi | >= 0.1.9 |
| Env loading | python-dotenv | >= 1.0.0 |
| Testing | pytest, pytest-asyncio | >= 8.0.0, >= 0.23.0 |
| Linting | ruff | >= 0.9.0 |
