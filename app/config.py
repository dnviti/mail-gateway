import re

from pydantic import field_validator
from pydantic_settings import BaseSettings

_RATE_LIMIT_PATTERN = re.compile(r"^\d+/(second|minute|hour|day)$")


class Settings(BaseSettings):
    APP_NAME: str = "mail-gateway"
    DEBUG: bool = False
    PORT: int = 8000

    STRIPE_WEBHOOK_SECRET: str = ""
    BREVO_API_KEY: str = ""
    ADMIN_API_KEY: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/mail_gateway"

    # Rate limiting (requests per minute)
    RATE_LIMIT_ADMIN: str = "60/minute"
    RATE_LIMIT_WEBHOOK: str = "100/minute"

    # Retention / TTL policy
    WEBHOOK_EVENTS_TTL_DAYS: int = 30
    DEAD_LETTER_TTL_DAYS: int = 90
    RETENTION_CLEANUP_INTERVAL_HOURS: int = 24
    RETENTION_BATCH_SIZE: int = 1000

    @field_validator("RATE_LIMIT_ADMIN", "RATE_LIMIT_WEBHOOK")
    @classmethod
    def validate_rate_limit_format(cls, v: str) -> str:
        if not _RATE_LIMIT_PATTERN.match(v):
            raise ValueError(
                f"Invalid rate limit format '{v}'. "
                "Expected '<number>/<second|minute|hour|day>' (e.g. '60/minute')."
            )
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
