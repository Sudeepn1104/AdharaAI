"""
routers/analyze.py — Document analysis endpoint.

Flow:
  1. Fetch the document by ID (must have been uploaded first)
  2. Segment raw text into clauses
  3. Risk-flag each clause using the hybrid rule+BERT pipeline
  4. Save clause-level results to the database
  5. Wipe raw_text immediately after analysis (privacy-first design)
  6. Return the analysis summary + clause results
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import logging

from backend.models.database import REDACTED_CLAUSE_TEXT, Document, Clause, get_db, wipe_expired_documents
from backend.services.document_access import require_document_access
from backend.services.clause_segmenter import segment_clauses
from backend.services.risk_flagger import flag_all_clauses, flag_all_clauses_hybrid, get_risk_summary
from backend.services.simplifier import simplify_all_clauses

logger = logging.getLogger("adharaai")
router = APIRouter()


@router.post("/{document_id}", summary="Run AI analysis on an uploaded document")
def analyze_document(document_id: int, document_token: str | None = Header(default=None, alias="X-Document-Token"), db: Session = Depends(get_db)):
    require_document_access(document_id, document_token)

    # Privacy housekeeping
    wipe_expired_documents(db)

    # Load document
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")
    if doc.raw_text_wiped or not doc.raw_text:
        raise HTTPException(
            status_code=410,
            detail=(
                "This document's raw text has been automatically deleted for privacy. "
                "Please re-upload the file to analyse it again."
            ),
        )

    # Step 1: Segment into clauses
    clauses = segment_clauses(doc.raw_text)
    if not clauses:
        raise HTTPException(
            status_code=422,
            detail="Could not detect individual clauses in this document. "
                   "Try uploading a cleaner copy or a text (.txt) version.",
        )

    # Step 2: Simplify language
    clauses = simplify_all_clauses(clauses)

    # Step 3: Hybrid risk flagging (rules + InLegalBERT), fail closed to rules-only
    try:
        clauses = flag_all_clauses_hybrid(clauses)
    except Exception as e:
        logger.error(f"Hybrid flagging failed, falling back to rules only: {e}", exc_info=True)
        clauses = flag_all_clauses(clauses)

    # Remove previous analysis if re-running
    db.query(Clause).filter(Clause.document_id == document_id).delete()

    saved_clauses = []
    for c in clauses:
        clause_row = Clause(
            document_id     = document_id,
            clause_number   = c.get("number"),
            original_text   = REDACTED_CLAUSE_TEXT,
            simplified_text = c.get("simplified_text"),
            clause_type     = c.get("bert_clause_type") or c.get("clause_type"),
            risk_level      = c.get("risk_level", "low"),
            risk_reason     = c.get("risk_reason"),
            risk_tip        = c.get("risk_tip"),
            confidence      = c.get("confidence", 100),
        )
        db.add(clause_row)
        saved_clauses.append(clause_row)

    # Privacy: wipe raw text immediately after successful analysis
    doc.raw_text        = None
    doc.raw_text_wiped  = True
    doc.analysed_at     = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    for c in saved_clauses:
        db.refresh(c)

    summary = get_risk_summary(clauses)

    logger.info(
        f"Analysed document {document_id}: "
        f"{len(clauses)} clauses, "
        f"overall_risk={summary.get('overall_risk')}"
    )

    return {
        "document_id": document_id,
        "filename":    doc.filename,
        "summary":     summary,
        "clauses": [
            {
                "number":      c.clause_number,
                "original":    None,
                "simplified":  c.simplified_text,
                "clause_type": c.clause_type,
                "risk_level":  c.risk_level,
                "risk_reason": c.risk_reason,
                "risk_tip":    c.risk_tip,
                "confidence":  c.confidence,
                "all_flags":   next((x.get("all_flags", []) for x in clauses if x.get("number") == c.clause_number), []),
            }
            for c in saved_clauses
        ],
    }


@router.get("/{document_id}", summary="Retrieve a previously saved analysis")
def get_analysis(document_id: int, document_token: str | None = Header(default=None, alias="X-Document-Token"), db: Session = Depends(get_db)):
    require_document_access(document_id, document_token)

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    clauses = db.query(Clause).filter(Clause.document_id == document_id).order_by(Clause.clause_number).all()
    if not clauses:
        raise HTTPException(status_code=404, detail="No analysis found for this document. Call POST first.")

    summary = get_risk_summary([
        {"risk_level": c.risk_level, "confidence": c.confidence} for c in clauses
    ])

    return {
        "document_id": doc.id,
        "filename":    doc.filename,
        "analysed_at": doc.analysed_at.isoformat() if doc.analysed_at else None,
        "summary":     summary,
        "clauses": [
            {
                "number":      c.clause_number,
                "original":    None,
                "simplified":  c.simplified_text,
                "clause_type": c.clause_type,
                "risk_level":  c.risk_level,
                "risk_reason": c.risk_reason,
                "risk_tip":    c.risk_tip,
                "confidence":  c.confidence,
            }
            for c in clauses
        ],
    }