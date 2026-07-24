"""
routers/analyze.py — NLP pipeline endpoint with confidence scoring.
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from backend.models.database import Document, Clause, get_db, wipe_expired_documents
from backend.services.clause_segmenter import segment_clauses
from backend.services.simplifier import simplify_all_clauses
from backend.services.risk_flagger import flag_all_clauses, get_risk_summary
import logging

logger = logging.getLogger("adharaai")
router = APIRouter()


@router.post("/{document_id}", summary="Run AI analysis on an uploaded document")
def analyze_document(document_id: int, db: Session = Depends(get_db)):

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

    # ── Pipeline ──────────────────────────────────────────────────────────────

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

    # Step 3: Flag risks with confidence scoring
    clauses = flag_all_clauses(clauses)

    # ── Persist results ───────────────────────────────────────────────────────

    # Remove previous analysis if re-running
    db.query(Clause).filter(Clause.document_id == document_id).delete()

    for c in clauses:
        db.add(Clause(
            document_id     = document_id,
            clause_number   = c["number"],
            original_text   = c["text"],
            simplified_text = c.get("simplified_text"),
            risk_level      = c.get("risk_level", "low"),
            risk_reason     = c.get("risk_reason"),
            risk_tip        = c.get("risk_tip"),
            confidence      = c.get("confidence", 100),
        ))

    # Privacy: wipe raw text immediately after successful analysis
    doc.raw_text        = None
    doc.raw_text_wiped  = True
    doc.analysed_at     = datetime.utcnow()
    db.commit()

    logger.info(
        f"Analysed document {document_id}: "
        f"{len(clauses)} clauses, "
        f"high={sum(1 for c in clauses if c.get('risk_level')=='high')}"
    )

    # ── Build response ────────────────────────────────────────────────────────
    summary = get_risk_summary(clauses)

    return {
        **summary,
        "document_id": document_id,
        "filename":    doc.filename,
        "clauses": [
            {
                "number":      c["number"],
                "original":    c["text"],
                "simplified":  c.get("simplified_text"),
                "risk_level":  c.get("risk_level", "low"),
                "risk_reason": c.get("risk_reason"),
                "risk_tip":    c.get("risk_tip"),
                "confidence":  c.get("confidence", 100),
                "all_flags":   c.get("all_flags", []),
            }
            for c in clauses
        ],
    }


@router.get("/{document_id}", summary="Retrieve a previously saved analysis")
def get_analysis(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    clauses = (
        db.query(Clause)
        .filter(Clause.document_id == document_id)
        .order_by(Clause.clause_number)
        .all()
    )
    if not clauses:
        raise HTTPException(
            status_code=404,
            detail="No analysis found for this document. Run POST /api/analyze/{id} first.",
        )

    return {
        "document_id": document_id,
        "filename":    doc.filename,
        "analysed_at": doc.analysed_at.isoformat() if doc.analysed_at else None,
        "clauses": [
            {
                "number":      c.clause_number,
                "original":    c.original_text,
                "simplified":  c.simplified_text,
                "risk_level":  c.risk_level,
                "risk_reason": c.risk_reason,
                "risk_tip":    c.risk_tip,
                "confidence":  c.confidence,
            }
            for c in clauses
        ],
    }
