"""
Central configuration — reads from .env file.
"""

from pydantic_settings import BaseSettings
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Predictive Healthcare Analytics"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./healthcare.db"
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")

    # Password Policy
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_EXPIRY_DAYS: int = 90
    MAX_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 30

    # Session
    SESSION_INACTIVITY_MINUTES: int = 30

    # Email Notifications
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    ALERT_EMAIL: str = ""

    # Federated Learning
    FL_ROUNDS: int = 5
    FL_MIN_CLIENTS: int = 2
    FL_SERVER_HOST: str = "localhost"
    FL_SERVER_PORT: int = 8080

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()