from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE, override=True)


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    TERMII_API_KEY: str = ""
    TERMII_SENDER_ID: str = "SmartBank"

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_SSL: bool = False
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = "noreply@smartbank.local"

    RESEND_API_KEY: str = ""
    RESEND_FROM_EMAIL: str = "noreply@smartbank.com"
    FRONTEND_URL: str = "http://localhost:8000"

    class Config:
        env_file = ENV_FILE


settings = Settings()
