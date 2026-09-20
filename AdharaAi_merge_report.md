# AdharaAI Merge Report

**Date:** 19 September 2026
**Scope:** token-based document access, privacy redaction, and upload safety.

## 1. Per-document authorization tokens

`backend/services/document_access.py` issues an HMAC-SHA256 token for each
uploaded document. The upload response returns this as `document_token`.

- Analyze (`POST` and `GET`) and delete routes require it in the
  `X-Document-Token` header.
- A token is bound to one document ID; it cannot be reused for another ID.
- Invalid or absent tokens receive HTTP 403.
- CORS permits `X-Document-Token` so the browser client can send it.

## 2. Privacy redaction and retention

- Upload responses no longer expose `text_preview`.
- After analysis, persisted `Clause.original_text` is replaced with the fixed
  redaction marker; saved-analysis responses return `original: null`.
- Startup redacts legacy clause text, and a periodic task invokes expiry cleanup
  even when no new requests arrive.
- The unauthenticated document-list endpoint was removed.

## 3. Safer uploads

- Upload bodies are read in 1 MB chunks and rejected with HTTP 413 when the
  configured limit is exceeded.
- Existing magic-byte MIME validation remains in force rather than trusting a
  filename or supplied content type.

## 4. OCR support

Scanned PDFs with insufficient digital text are rendered page by page and sent
to Tesseract (maximum 25 pages). Image OCR supports JPEG, PNG, TIFF, and BMP.
The Render deployment uses the repository Dockerfile, which installs the
native `tesseract-ocr` package.

## 5. Deployment safeguards

Render generates `APP_SECRET_KEY`; production startup now fails if that
variable is missing, a known development placeholder, or shorter than 32
characters. Dependency constraints explicitly pin FastAPI's matching
Starlette and Pydantic releases to keep fresh installs deterministic.
