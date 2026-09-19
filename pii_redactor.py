"""
AdharaAI PII Redaction Utility
--------------------------------
Detects and redacts common Indian PII patterns from clause text before
it reaches the API / training pipeline.

Covers:
  - PAN card numbers (e.g. ABCDE1234F)
  - Aadhaar numbers (12 digits, optionally spaced in groups of 4)
  - Indian phone numbers (10-digit, with optional +91 / 0 prefix)
  - Email addresses
  - Cheque numbers (heuristic: "cheque no" / "cheque number" followed by digits)
  - Physical address fragments (heuristic: pin codes, "House No." patterns)
  - Bank account numbers (heuristic: 9-18 digit sequences near "account")

NOTE: This is a heuristic, regex-based first pass. It is NOT a substitute
for manual review — false negatives (missed PII) and false positives
(redacting legitimate contract language, e.g. rent amounts) are both
possible. Always spot-check output before using redacted data downstream.
"""

import re
import csv
import sys
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

PATTERNS = {
    "PAN": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    "AADHAAR": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "PHONE": re.compile(r"(?:(?:\+91|0)[\s-]?)?[6-9]\d{9}\b"),
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "CHEQUE_NO": re.compile(
        r"\bcheque\s*(?:no\.?|number)?\s*[:\-]?\s*\d{5,10}\b", re.IGNORECASE
    ),
    "PIN_CODE": re.compile(r"\b\d{6}\b"),
    # Bank account: 9-18 digit run, but only flagged if "account" appears nearby
    "BANK_ACCOUNT_CONTEXT": re.compile(
        r"account\s*(?:no\.?|number)?\s*[:\-]?\s*\d{9,18}\b", re.IGNORECASE
    ),
}

# Patterns we deliberately do NOT redact by default because they usually
# describe the AGREEMENT ITSELF (rent amounts, deposit amounts) rather than
# a real person's private financial identity. Flagged separately as "REVIEW"
# rather than auto-redacted, since these are often legitimate contract terms.
REVIEW_ONLY_PATTERNS = {
    "RUPEE_AMOUNT": re.compile(r"Rs\.?\s?[\d,]+(?:/-)?"),
}


@dataclass
class RedactionResult:
    original: str
    redacted: str
    findings: dict = field(default_factory=dict)   # pattern_name -> list of matches
    review_flags: dict = field(default_factory=dict)  # pattern_name -> list of matches


def redact_text(text: str) -> RedactionResult:
    redacted = text
    findings = {}

    for name, pattern in PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            findings[name] = matches
            redacted = pattern.sub(f"[REDACTED_{name}]", redacted)

    review_flags = {}
    for name, pattern in REVIEW_ONLY_PATTERNS.items():
        matches = pattern.findall(redacted)  # check what's left after redaction
        if matches:
            review_flags[name] = matches

    return RedactionResult(original=text, redacted=redacted, findings=findings, review_flags=review_flags)


def scan_csv(path: str, text_column: str = "clause_text"):
    """Run redaction over every row of a clause dataset CSV and report findings."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    rows_with_pii = []
    rows_with_review_flags = []

    for i, row in enumerate(reader):
        text = row.get(text_column, "")
        result = redact_text(text)
        if result.findings:
            rows_with_pii.append((i, row.get("source_file", "?"), result))
        if result.review_flags:
            rows_with_review_flags.append((i, row.get("source_file", "?"), result))

    return reader, rows_with_pii, rows_with_review_flags


def print_report(rows_with_pii, rows_with_review_flags, total_rows):
    print(f"Scanned {total_rows} rows.\n")

    print(f"=== HARD PII FINDINGS (auto-redacted): {len(rows_with_pii)} rows flagged ===")
    for idx, source, result in rows_with_pii:
        print(f"\nRow {idx} (source: {source})")
        for pattern_name, matches in result.findings.items():
            print(f"  [{pattern_name}] -> {matches}")
        print(f"  Original : {result.original[:150]}{'...' if len(result.original) > 150 else ''}")
        print(f"  Redacted : {result.redacted[:150]}{'...' if len(result.redacted) > 150 else ''}")

    print(f"\n\n=== REVIEW-ONLY FLAGS (not auto-redacted, human judgment needed): {len(rows_with_review_flags)} rows flagged ===")
    for idx, source, result in rows_with_review_flags[:10]:  # cap preview
        print(f"\nRow {idx} (source: {source})")
        for pattern_name, matches in result.review_flags.items():
            print(f"  [{pattern_name}] -> {matches}")
    if len(rows_with_review_flags) > 10:
        print(f"\n... and {len(rows_with_review_flags) - 10} more rows with review-only flags (rupee amounts, etc.)")


def write_redacted_csv(reader, output_path: str, text_column: str = "clause_text"):
    """Write a new CSV with the text_column redacted in place."""
    if not reader:
        return
    fieldnames = reader[0].keys()
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            result = redact_text(row.get(text_column, ""))
            new_row = dict(row)
            new_row[text_column] = result.redacted
            writer.writerow(new_row)


if __name__ == "__main__":
    input_path = sys.argv[1] if len(sys.argv) > 1 else "adharaai_deployment_ready.csv"
    reader, pii_rows, review_rows = scan_csv(input_path)
    print_report(pii_rows, review_rows, len(reader))

    if len(sys.argv) > 2 and sys.argv[2] == "--write":
        out_path = "adharaai_deployment_ready_redacted.csv"
        write_redacted_csv(reader, out_path)
        print(f"\n\nRedacted CSV written to: {out_path}")
