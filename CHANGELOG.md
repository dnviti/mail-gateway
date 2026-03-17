# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.1] - 2026-03-17

### Added

- Mail gateway with Stripe webhook and Brevo email integration (MAIL-0001)
- Welcome email on first Stripe subscription purchase
- Subscription lifecycle email events: cancellation, payment failure, renewal reminder, plan change (MAIL-0004)
- Webhook idempotency guard with atomic duplicate detection (WBHK-0002)
- Email delivery retry with exponential backoff and dead letter queue (INFRA-0003)
- Webhook event audit log with admin query endpoint (SEC-0005)
- Database table retention/TTL policy for webhook events and dead letters (RPAT-0002)
- Rate limiting on admin and webhook endpoints via slowapi (RPAT-0003)
- PII redaction in logs and payload storage for GDPR compliance (RPAT-0004)

### Changed

- Shared httpx.AsyncClient with proper lifecycle management (RPAT-0005)
- Pydantic response models for audit endpoint (RPAT-0005)
- Stripe event ID format validation in idempotency guard (RPAT-0005)
- Sender email configuration validation (RPAT-0005)

### Fixed

- CI/CD pipelines configured for Python 3.12/FastAPI (CICD-0006)
- Added ruff linter, split dependencies, pinned Docker Actions to commit SHAs (RPAT-0001)

[Unreleased]: https://github.com/dnviti/mail-gateway/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/dnviti/mail-gateway/releases/tag/v0.0.1
