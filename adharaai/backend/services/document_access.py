"""Signed, per-document access tokens for the unauthenticated public API."""

import hashlib
import hmac

from fastapi import HTTPException

from config import settings


def issue_document_token(document_id: int) -> str:
    """Create a bearer token that grants access only to one document."""
    document_id_value = str(document_id)
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        document_id_value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{document_id_value}.{signature}"


def has_document_access(document_id: int, token: str | None) -> bool:
    """Return whether a token is valid for the requested document."""
    if not token:
        return False

    token_document_id, separator, signature = token.partition(".")
    if not separator or token_document_id != str(document_id):
        return False

    expected_token = issue_document_token(document_id)
    return hmac.compare_digest(token, expected_token)


def require_document_access(document_id: int, token: str | None) -> None:
    """Raise a consistent API error when a document token is missing or invalid."""
    if not has_document_access(document_id, token):
        raise HTTPException(
            status_code=403,
            detail="A valid X-Document-Token is required to access this document.",
        )
