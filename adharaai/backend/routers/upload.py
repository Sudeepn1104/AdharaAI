"""
routers/upload.py — Secure file upload endpoint.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from backend.models.database import Document, get_db, wipe_expired_documents
from backend.services.document_access import issue_document_token
from backend.services.text_extractor import extract_text, count_words
from config import settings
import logging

logger = logging.getLogger("adharaai")
router = APIRouter()


@router.post("/", summary="Upload a legal document for analysis")
async def upload_document(
    file: UploadFile = File(..., description="PDF, TXT, JPG, or PNG — max 10 MB"),
    db: Session = Depends(get_db),
):
    # Auto-clean expired documents (privacy housekeeping)
    wiped = wipe_expired_documents(db)
    if wiped:
        logger.info(f"Auto-wiped raw text from {wiped} expired document(s)")

    # Read file content without accepting an unbounded request into memory.
    try:
        content = bytearray()
        while chunk := await file.read(1024 * 1024):
            content.extend(chunk)
            if len(content) > settings.MAX_FILE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum allowed size is {settings.MAX_FILE_BYTES // (1024 * 1024)} MB.",
                )
        file_bytes = bytes(content)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read the uploaded file.")

    # Extract and validate
    try:
        raw_text = extract_text(file.filename or "upload.txt", file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not raw_text or len(raw_text.strip()) < 60:
        raise HTTPException(
            status_code=422,
            detail=(
                "Could not extract enough text from this file. "
                "Try a clearer scan, a text-based PDF, or paste the content as a .txt file."
            ),
        )

    # Save with TTL for privacy
    expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=settings.DOCUMENT_TTL)
    doc = Document(
        filename       = file.filename or "upload",
        raw_text       = raw_text,
        char_count     = len(raw_text),
        expires_at     = expires,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    logger.info(f"Document uploaded: id={doc.id}, chars={len(raw_text)}, expires={expires.isoformat()}")

    return {
        "document_id":   doc.id,
        "filename":      doc.filename,
        "char_count":    len(raw_text),
        "word_count":    count_words(raw_text),
        "document_token": issue_document_token(doc.id),
        "expires_in":    f"Raw text auto-deleted in {settings.DOCUMENT_TTL // 60} minutes",
        "message":       "Upload successful. Keep the document token to analyse or delete this document.",
    }
