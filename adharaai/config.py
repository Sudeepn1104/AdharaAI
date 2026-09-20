"""
config.py — single source of truth for all settings.
Reads from environment variables / .env file.
"""
import os
import secrets
from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_ENV: str            = os.getenv("APP_ENV", "development")
    APP_VERSION: str        = os.getenv("APP_VERSION", "1.0.0")
    IS_PROD: bool           = APP_ENV == "production"

    # Document-access tokens are signed with this key. A development key is
    # intentionally ephemeral; production requires a durable supplied secret.
    _configured_secret: str | None = os.getenv("APP_SECRET_KEY")
    if IS_PROD and (
        not _configured_secret
        or _configured_secret in {
            "dev-secret-change-in-prod",
            "change-this-to-a-long-random-string-in-production",
        }
        or len(_configured_secret) < 32
    ):
        raise RuntimeError(
            "APP_SECRET_KEY must be a strong, unique value of at least 32 characters in production."
        )
    SECRET_KEY: str = _configured_secret or secrets.token_urlsafe(48)

    # Database
    DATABASE_URL: str       = os.getenv("DATABASE_URL", "sqlite:///./adharaai.db")

    # Privacy — auto-delete raw document text after N seconds
    DOCUMENT_TTL: int       = int(os.getenv("DOCUMENT_TTL_SECONDS", "300"))

    # Rate limiting
    RATE_LIMIT: str         = os.getenv("RATE_LIMIT_PER_MINUTE", "10")

    # File uploads
    MAX_FILE_BYTES: int     = int(os.getenv("MAX_FILE_SIZE_MB", "10")) * 1024 * 1024
    ALLOWED_EXTENSIONS: set = set(os.getenv(
        "ALLOWED_EXTENSIONS", "pdf,txt,png,jpg,jpeg,tiff,bmp"
    ).split(","))

    # MIME types that map to allowed extensions
    ALLOWED_MIME_TYPES: set = {
        "application/pdf",
        "text/plain",
        "image/jpeg",
        "image/png",
        "image/tiff",
        "image/bmp",
    }

    # OCR
    TESSERACT_CMD: str      = os.getenv("TESSERACT_CMD", "tesseract")

    # CORS
    ALLOWED_ORIGINS: list   = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:5500,http://127.0.0.1:8000"
    ).split(",")


settings = Settings()
