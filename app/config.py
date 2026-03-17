from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "mail-gateway"
    DEBUG: bool = False
    PORT: int = 8000

    STRIPE_WEBHOOK_SECRET: str = ""
    BREVO_API_KEY: str = ""
    ADMIN_API_KEY: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/mail_gateway"

    # PII redaction — enabled by default for GDPR compliance.
    # Set to false only in development/debugging environments.
    PII_REDACTION_ENABLED: bool = True
    # Salt for PII correlation hashes.  Set a unique, secret value per
    # deployment to prevent rainbow-table reversal of hashed PII.
    PII_HASH_SALT: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
