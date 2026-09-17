  limit is exceeded.
- The existing content-based MIME validation remains in place.

Affected file: `adharaai/backend/routers/upload.py`.

### 4. Scanned-PDF OCR and image support

- Added PyMuPDF (`PyMuPDF==1.28.0`) to both root and nested requirements files.
- Added a scanned-PDF path: PDFs with insufficient digital text are rendered
  page-by-page and sent through Tesseract OCR.
- Limited scanned PDFs to 25 pages.
- Added BMP magic-byte validation and configuration support.
- Added `TESSERACT_CMD`, including Windows default-install discovery and a
  clear user-facing error when Tesseract is unavailable.

Affected files:

- `adharaai/backend/services/text_extractor.py`
- `config.py`
- `adharaai/config.py`
- `requirements.txt`
- `adharaai/requirements.txt`

### 5. Small compatibility and operational improvements

- Added a permanent redirect from `/privacy.html` to `/privacy`.
- Replaced the Unicode request-log arrow with ASCII `->`; this prevents
  `UnicodeEncodeError` on Windows consoles using a non-UTF-8 code page.

Affected files:

- `main.py`
- `adharaai/main.py`
- `adharaai/backend/middleware/security.py`

## Verification performed

1. Parsed all changed Python files with `ast.parse`: **passed**.
2. Imported and exercised the document-token helper: **passed**.
   - Valid token for document 42 accepted.
   - Same token for document 43 rejected.
   - Invalid token rejected.
3. Imported the scanned-PDF OCR path using the available virtual environment:
   **passed**.
4. Ran an end-to-end API verification against a temporary SQLite database:
   **passed**.
   - Upload returned 200 and a document token.
   - Upload response omitted `text_preview`.
   - Analyze without the token returned 403.
   - Analyze with the token returned 200.
   - Saved analysis returned 200 and exposed no original clause text.
   - Delete without the token returned 403.
   - Delete with the token returned 200.
5. Ran `git diff --check`: **passed** (no whitespace errors).

The temporary verification database was removed after the test.

## Intentionally preserved target-repository work

The following AdharaAI-specific work was deliberately retained:

- Expanded employment, rental, and court-notice risk rules.
- Dataset and redaction utilities.
- Deployment-oriented root application layout.
- Existing test and data files not related to the privacy/access merge.

## Remaining follow-ups

1. Install target dependencies before deployment; the target's active local
   Python environment did not have FastAPI available, so functional checks used
   the compatible virtual environment from the source project. No dependency
   installation was performed in this session.
2. Ensure production sets a strong, unique `APP_SECRET_KEY`. Tokens are signed
   with this key; the development default must not be used in production.
3. Install Tesseract on deployment hosts if scanned-PDF/image OCR is required.
   Set `TESSERACT_CMD` when it is not available on `PATH`.
4. `adharaai/new_rules_batch.py` remains an invalid standalone Python fragment
   (`IndentationError` at line 3). It was present before this merge and was not
   modified. Convert it to a valid module or data file before running an
   all-files compile check.
5. The pre-existing modified file
   `adharaai/backend/__pycache__/__init__.cpython-313.pyc` was not changed or
   reverted.

## Files changed in the target repository

- `adharaai/backend/services/document_access.py` (new)
- `adharaai/backend/services/text_extractor.py`
- `adharaai/backend/middleware/security.py`
- `adharaai/backend/models/database.py`
- `adharaai/backend/routers/analyze.py`
- `adharaai/backend/routers/documents.py`
- `adharaai/backend/routers/upload.py`
- `adharaai/config.py`
- `adharaai/main.py`
- `adharaai/requirements.txt`
- `config.py`
- `main.py`
- `requirements.txt`
