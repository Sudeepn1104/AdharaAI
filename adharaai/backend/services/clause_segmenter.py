"""
clause_segmenter.py — Multi-strategy clause detection for Indian legal docs.

Strategy waterfall (tried in order, first success wins):
  1. Numbered heading detection   ("1.", "Clause 1", "Article 5")
  2. Lettered sub-clause detection ("(a)", "(i)")
  3. WHEREAS / NOW THEREFORE blocks
  4. Blank-line paragraph splitting
  5. Sentence-length chunking (fallback)

Post-processing:
  - Remove fragments under 30 characters
  - Merge orphan lines into previous clause
  - Deduplicate
"""

import re
import unicodedata


# ── Pre-processing ────────────────────────────────────────────────────────────

def normalise(text: str) -> str:
    """Clean up common OCR and PDF extraction artefacts."""
    # Normalise unicode (handles ﬁ ligatures etc.)
    text = unicodedata.normalize("NFKC", text)
    # Remove null bytes
    text = text.replace("\x00", "")
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)
    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Remove page numbers (common in PDFs): lone number on a line
    text = re.sub(r"^\s*\d{1,3}\s*$", "", text, flags=re.MULTILINE)
    # Remove common PDF header/footer patterns
    text = re.sub(r"Page\s+\d+\s+of\s+\d+", "", text, flags=re.IGNORECASE)
    return text.strip()


# ── Pattern definitions ───────────────────────────────────────────────────────

# Patterns that START a new clause
CLAUSE_STARTERS = [
    # "1." / "1)" / "1:"
    r"^\s*(\d{1,2})\s*[.)]\s+[A-Z\(]",
    # "1.1" / "1.1." sub-clauses
    r"^\s*\d{1,2}\.\d{1,2}\.?\s+[A-Z\(]",
    # "Clause 1" / "CLAUSE ONE"
    r"^\s*(Clause|CLAUSE)\s+(\d+|[A-Z]+)\b",
    # "Article 5" / "ARTICLE V"
    r"^\s*(Article|ARTICLE)\s+(\d+|[IVXLC]+)\b",
    # "Section 3" / "SECTION 3"
    r"^\s*(Section|SECTION)\s+\d+\b",
    # "A." / "B." (lettered top-level clauses)
    r"^\s*[A-Z]\.\s+[A-Z]",
    # "WHEREAS" (recitals)
    r"^\s*WHEREAS[,\s]",
    # "NOW, THEREFORE" / "NOW THEREFORE"
    r"^\s*NOW,?\s+THEREFORE",
    # "IN WITNESS WHEREOF"
    r"^\s*IN\s+WITNESS\s+WHEREOF",
    # ALL-CAPS heading (e.g. "PAYMENT TERMS:")
    r"^\s*[A-Z][A-Z\s]{4,}:\s*$",
]

COMBINED = re.compile("|".join(CLAUSE_STARTERS), re.MULTILINE)


# ── Segmentation strategies ───────────────────────────────────────────────────

def _by_numbered_headings(lines: list) -> list:
    """Strategy 1: Split at numbered/headed clause boundaries."""
    text = "\n".join(lines)
    splits = list(COMBINED.finditer(text))
    if len(splits) < 2:
        return []

    clauses = []
    for i, match in enumerate(splits):
        start = match.start()
        end   = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        chunk = text[start:end].strip()
        if len(chunk) > 40:
            clauses.append(chunk)
    return clauses


def _by_blank_lines(lines: list) -> list:
    """Strategy 2: Split on blank lines (paragraph-style documents)."""
    clauses, current = [], []
    for line in lines:
        if line.strip() == "":
            if current:
                block = " ".join(current).strip()
                if len(block) > 40:
                    clauses.append(block)
                current = []
        else:
            current.append(line.strip())
    if current:
        block = " ".join(current).strip()
        if len(block) > 40:
            clauses.append(block)
    return clauses


def _by_sentence_chunks(text: str, target_len: int = 400) -> list:
    """Strategy 3: Fallback — split into ~400-char sentence groups."""
    # Simple sentence split on . ! ? followed by space + capital
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z(])', text)
    clauses, current = [], ""
    for sent in sentences:
        current += " " + sent
        if len(current) >= target_len:
            clauses.append(current.strip())
            current = ""
    if current.strip():
        clauses.append(current.strip())
    return [c for c in clauses if len(c) > 40]


# ── Post-processing ───────────────────────────────────────────────────────────

def _clean_clauses(raw: list) -> list:
    """Remove noise, merge orphans, deduplicate."""
    cleaned = []
    seen = set()
    for c in raw:
        c = re.sub(r"\s+", " ", c).strip()
        if len(c) < 40:
            # Merge very short fragments into previous clause
            if cleaned:
                cleaned[-1] = cleaned[-1] + " " + c
            continue
        fingerprint = c[:60].lower()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        cleaned.append(c)
    return cleaned


# ── Public API ────────────────────────────────────────────────────────────────

def segment_clauses(raw_text: str) -> list:
    """
    Main entry point.
    Returns: [{"number": int, "text": str}, ...]
    """
    text  = normalise(raw_text)
    lines = text.split("\n")

    # Try strategies in order
    clauses = _by_numbered_headings(lines)
    if len(clauses) < 2:
        clauses = _by_blank_lines(lines)
    if len(clauses) < 2:
        clauses = _by_sentence_chunks(text)

    if len(clauses) < 2:
        clauses = _by_period_sentences(text)
    clauses = _clean_clauses(clauses)

    return [
        {"number": i + 1, "text": clause}
        for i, clause in enumerate(clauses)
    ]


def _by_period_sentences(text: str) -> list:
    """Strategy 4: Split on '. ' followed by capital — handles single-paragraph docs."""
    parts = re.split(r'\.\s+(?=[A-Z])', text)
    result = []
    for p in parts:
        p = p.strip()
        if p and not p.endswith('.'):
            p += '.'
        if len(p) > 40:
            result.append(p)
    return result
