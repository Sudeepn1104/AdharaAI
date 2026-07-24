"""
config.py — single source of truth for all settings.
Reads from environment variables / .env file.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_ENV: str            = os.getenv("APP_ENV", "development")
    APP_VERSION: str        = os.getenv("APP_VERSION", "1.0.0")
    SECRET_KEY: str         = os.getenv("APP_SECRET_KEY", "dev-secret-change-in-prod")
    IS_PROD: bool           = APP_ENV == "production"

    # Database
    DATABASE_URL: str       = os.getenv("DATABASE_URL", "sqlite:///./adharaai.db")

    # Privacy — auto-delete raw document text after N seconds
    DOCUMENT_TTL: int       = int(os.getenv("DOCUMENT_TTL_SECONDS", "300"))

    # Rate limiting
    RATE_LIMIT: str         = os.getenv("RATE_LIMIT_PER_MINUTE", "10")

    # File uploads
    MAX_FILE_BYTES: int     = int(os.getenv("MAX_FILE_SIZE_MB", "10")) * 1024 * 1024
    ALLOWED_EXTENSIONS: set = set(os.getenv(
        "ALLOWED_EXTENSIONS", "pdf,txt,png,jpg,jpeg,tiff"
    ).split(","))

    # MIME types that map to allowed extensions
    ALLOWED_MIME_TYPES: set = {
        "application/pdf",
        "text/plain",
        "image/jpeg",
        "image/png",
        "image/tiff",
    }

    # CORS
    ALLOWED_ORIGINS: list   = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:5500,http://127.0.0.1:8000"
    ).split(",")


settings = Settings()
