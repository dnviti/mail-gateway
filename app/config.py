from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "mail-gateway"
    DEBUG: bool = False
    PORT: int = 8000

    STRIPE_WEBHOOK_SECRET: str = ""
    BREVO_API_KEY: str = ""
    ADMIN_API_KEY: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://localhost:5432/mail_gateway"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
