"""
text_extractor.py — Secure document text extraction.
Validates file type by content (magic bytes), not just extension.
"""
import io
import os
import re
from pathlib import Path
import fitz
import pytesseract
from PIL import Image
from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from config import settings


# Magic bytes for allowed file types
MAGIC_SIGNATURES = {
    b"%PDF":           "application/pdf",
    b"\xff\xd8\xff":   "image/jpeg",
    b"\x89PNG\r\n":    "image/png",
    b"II*\x00":        "image/tiff",
    b"MM\x00*":        "image/tiff",
    b"BM":              "image/bmp",
}
MAX_SCANNED_PDF_PAGES = 25


def detect_mime(file_bytes: bytes) -> str:
    """Detect MIME type from file magic bytes — NOT the filename."""
    for magic, mime in MAGIC_SIGNATURES.items():
        if file_bytes[:len(magic)] == magic:
            return mime
    # Check if it's valid UTF-8 text
    try:
        file_bytes[:512].decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError:
        return "application/octet-stream"


def validate_file(filename: str, file_bytes: bytes) -> None:
    """
    Raises ValueError with a user-friendly message if file is invalid.
    Checks: size, extension, MIME type (by content), and basic structure.
    """
    # 1. Size check
    if len(file_bytes) > settings.MAX_FILE_BYTES:
        raise ValueError(
            f"File too large. Maximum allowed size is "
            f"{settings.MAX_FILE_BYTES // (1024*1024)} MB."
        )

    # 2. Extension check
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise ValueError(
            f"File type '.{ext}' is not supported. "
            f"Allowed types: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}"
        )

    # 3. MIME check (content-based — cannot be spoofed by renaming)
    actual_mime = detect_mime(file_bytes)
    if actual_mime not in settings.ALLOWED_MIME_TYPES and actual_mime != "text/plain":
        raise ValueError(
            "File content does not match the expected type. "
            "Please upload a genuine PDF, image, or text file."
        )

    # 4. Empty file check
    if len(file_bytes) < 50:
        raise ValueError("The uploaded file appears to be empty or too small.")


def extract_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a digital (non-scanned) PDF."""
    output = io.StringIO()
    try:
        extract_text_to_fp(
            io.BytesIO(file_bytes),
            output,
            laparams=LAParams(line_margin=0.5, word_margin=0.1),
            output_type="text",
            codec="utf-8",
        )
    except Exception as e:
        raise ValueError(f"Could not read this PDF: {e}")
    return output.getvalue().strip()


def extract_text_from_image(image: Image.Image) -> str:
    """Extract text from an already decoded image using Tesseract OCR."""
    try:
        tesseract_cmd = settings.TESSERACT_CMD
        if os.name == "nt" and tesseract_cmd == "tesseract":
            installed_command = Path(os.getenv("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR" / "tesseract.exe"
            if installed_command.is_file():
                tesseract_cmd = str(installed_command)
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        pytesseract.get_tesseract_version()
        # Upscale small images for better OCR accuracy
        w, h = image.size
        if w < 1000:
            scale = 1000 / w
            image = image.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        # Convert to grayscale for better accuracy
        image = image.convert("L")
        text = pytesseract.image_to_string(image, lang="eng", config="--psm 6")
        return text.strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise ValueError("Image OCR requires Tesseract. Install it and set TESSERACT_CMD if it is not on PATH.") from exc
    except Exception as e:
        raise ValueError(f"Could not read this image: {e}")


def extract_from_image(file_bytes: bytes) -> str:
    """Extract text from a scanned image using Tesseract OCR."""
    try:
        return extract_text_from_image(Image.open(io.BytesIO(file_bytes)))
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not read this image: {e}")


def extract_from_scanned_pdf(file_bytes: bytes) -> str:
    """Render a scanned PDF into images and extract text from each page."""
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as document:
            if not document.page_count:
                raise ValueError("The PDF does not contain any pages.")
            if document.page_count > MAX_SCANNED_PDF_PAGES:
                raise ValueError(f"Scanned PDFs are limited to {MAX_SCANNED_PDF_PAGES} pages.")
            extracted_pages = []
            for page in document:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                extracted_pages.append(extract_text_from_image(Image.open(io.BytesIO(pixmap.tobytes("png")))))
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not render this scanned PDF: {e}")
    return "\n\n".join(page for page in extracted_pages if page).strip()


def extract_text(filename: str, file_bytes: bytes) -> str:
    """
    Main entry. Validates file then extracts text.
    Returns clean extracted text string.
    """
    validate_file(filename, file_bytes)

    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "pdf":
        text = extract_from_pdf(file_bytes)
        # If digital extraction got almost nothing, it's a scanned PDF
        if len(text.strip()) < 100:
            return extract_from_scanned_pdf(file_bytes)
        return text

    elif ext in ("jpg", "jpeg", "png", "tiff", "bmp"):
        return extract_from_image(file_bytes)

    elif ext == "txt":
        try:
            return file_bytes.decode("utf-8", errors="replace").strip()
        except Exception:
            raise ValueError("Could not read this text file.")

    else:
        raise ValueError(f"Unsupported file type: .{ext}")


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))
