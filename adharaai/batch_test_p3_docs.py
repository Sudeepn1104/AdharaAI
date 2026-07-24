"""
batch_test_p3_docs.py
======================
Batch-tests all .docx documents in a folder against AdharaAI's risk flagger.
No ground-truth labels needed — this is a PRECISION spot-check: it runs every
document through your real pipeline (segment -> flag) and gives you an
aggregate summary plus a detailed CSV so you can manually review flags for
obvious false positives or false negatives across all 43 documents at once.

SETUP (run once):
    pip install python-docx

USAGE:
    Place this script inside your project root:
    C:\\Users\\Sudeep Nayak\\Desktop\\AdharaAI\\adharaai\\batch_test_p3_docs.py

    Then run:
    python batch_test_p3_docs.py

    It expects your documents in:
    data\\p3_documents\\*.docx

OUTPUT:
    - Console summary: per-document clause counts and risk breakdown
    - batch_test_results.csv: every single clause from every document, with
      its risk level, reason, and confidence — for manual review
"""

import os
import sys
import csv
import glob

# Make sure we can import your existing backend modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from docx import Document
except ImportError:
    print("ERROR: python-docx is not installed.")
    print("Run this first:  pip install python-docx")
    sys.exit(1)

try:
    from backend.services.clause_segmenter import segment_clauses
    from backend.services.risk_flagger import flag_clause
except ImportError as e:
    print(f"ERROR: could not import backend modules ({e})")
    print("Make sure this script is placed in your project ROOT folder")
    print("(the same folder as main.py), not inside a subfolder.")
    sys.exit(1)


def extract_text_from_docx(path: str) -> str:
    """Extract all paragraph text from a .docx file."""
    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def main():
    docs_folder = os.path.join("data", "p3_documents")
    docx_files = sorted(glob.glob(os.path.join(docs_folder, "*.docx")))

    if not docx_files:
        print(f"No .docx files found in {docs_folder}")
        print("Check the folder path and try again.")
        sys.exit(1)

    print(f"Found {len(docx_files)} documents. Processing...\n")

    all_rows = []
    doc_summaries = []

    for i, filepath in enumerate(docx_files, 1):
        filename = os.path.basename(filepath)
        try:
            text = extract_text_from_docx(filepath)
        except Exception as e:
            print(f"  [{i}/{len(docx_files)}] {filename} -> FAILED TO READ ({e})")
            continue

        if not text.strip():
            print(f"  [{i}/{len(docx_files)}] {filename} -> EMPTY (no text extracted)")
            continue

        try:
            clauses = segment_clauses(text)
        except Exception as e:
            print(f"  [{i}/{len(docx_files)}] {filename} -> SEGMENTATION FAILED ({e})")
            continue

        high = medium = low = 0

        for c_idx, clause_text in enumerate(clauses, 1):
            # segment_clauses may return strings or dicts depending on your
            # implementation -- handle both
            if isinstance(clause_text, dict):
                text_for_flagging = clause_text.get("text", "")
            else:
                text_for_flagging = clause_text

            result = flag_clause(text_for_flagging)
            level = result["risk_level"]

            if level == "high":
                high += 1
            elif level == "medium":
                medium += 1
            else:
                low += 1

            all_rows.append({
                "source_file": filename,
                "clause_number": c_idx,
                "clause_text": text_for_flagging[:300],
                "risk_level": level,
                "risk_reason": result.get("risk_reason") or "",
                "risk_tip": result.get("risk_tip") or "",
                "confidence": result.get("confidence", ""),
            })

        total = high + medium + low
        print(f"  [{i}/{len(docx_files)}] {filename} -> "
              f"{total} clauses | {high} high, {medium} medium, {low} low")

        doc_summaries.append({
            "file": filename,
            "total_clauses": total,
            "high": high,
            "medium": medium,
            "low": low,
        })

    # Write detailed CSV for manual review
    output_csv = "batch_test_results.csv"
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "source_file", "clause_number", "clause_text",
            "risk_level", "risk_reason", "risk_tip", "confidence"
        ])
        writer.writeheader()
        writer.writerows(all_rows)

    # Aggregate summary
    total_clauses = sum(d["total_clauses"] for d in doc_summaries)
    total_high = sum(d["high"] for d in doc_summaries)
    total_medium = sum(d["medium"] for d in doc_summaries)
    total_low = sum(d["low"] for d in doc_summaries)

    print("\n" + "=" * 60)
    print("BATCH TEST SUMMARY")
    print("=" * 60)
    print(f"  Documents processed : {len(doc_summaries)}")
    print(f"  Total clauses       : {total_clauses}")
    print(f"  High risk           : {total_high} ({total_high/total_clauses*100:.1f}%)" if total_clauses else "  High risk           : 0")
    print(f"  Medium risk         : {total_medium} ({total_medium/total_clauses*100:.1f}%)" if total_clauses else "  Medium risk         : 0")
    print(f"  Low risk (clear)    : {total_low} ({total_low/total_clauses*100:.1f}%)" if total_clauses else "  Low risk (clear)    : 0")
    print(f"\n  Detailed results written to: {output_csv}")
    print("  Open this in Excel and manually review flagged clauses for")
    print("  false positives (flagged but actually fine) or obvious misses")
    print("  (risky clauses that came back as 'low').")
    print("=" * 60)


if __name__ == "__main__":
    main()
