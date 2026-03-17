import re

from pydantic_settings import BaseSettings

# Basic email format check (RFC 5322 simplified)
_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class Settings(BaseSettings):
    APP_NAME: str = "mail-gateway"
    DEBUG: bool = False
    PORT: int = 8000

    STRIPE_WEBHOOK_SECRET: str = ""
    BREVO_API_KEY: str = ""
    ADMIN_API_KEY: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/mail_gateway"

    # Optional override for the sender email address.
    # When not set, the sender email is derived as noreply@{APP_NAME}.com.
    SENDER_EMAIL: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def sender_email(self) -> str:
        """Return a validated sender email address.

        Uses SENDER_EMAIL if configured, otherwise derives one from APP_NAME.
        Raises ValueError if the resulting address is not a valid email format.
        """
        email = self.SENDER_EMAIL or f"noreply@{self.APP_NAME}.com"
        if not _EMAIL_PATTERN.match(email):
            raise ValueError(
                f"Invalid sender email '{email}'. Set a valid SENDER_EMAIL "
                f"or ensure APP_NAME produces a valid domain."
            )
        return email


settings = Settings()
