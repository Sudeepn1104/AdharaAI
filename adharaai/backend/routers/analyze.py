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
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from backend.models.database import Document, Clause, get_db, wipe_expired_documents
from backend.services.clause_segmenter import segment_clauses
from backend.services.risk_flagger import flag_all_clauses_hybrid, get_risk_summary
from backend.services.simplifier import simplify_all_clauses

logger = logging.getLogger("adharaai")
router = APIRouter()


@router.post("/{document_id}", summary="Analyse an uploaded document")
async def analyze_document(document_id: int, db: Session = Depends(get_db)):
    # Auto-clean expired documents (privacy housekeeping)
    wiped = wipe_expired_documents(db)
    if wiped:
        logger.info(f"Auto-wiped raw text from {wiped} expired document(s)")

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.raw_text_wiped or not doc.raw_text:
        raise HTTPException(
            status_code=410,
            detail="This document's text has already been wiped (privacy TTL). Please upload again.",
        )

    # Segment into clauses
    clauses = segment_clauses(doc.raw_text)
    if not clauses:
        raise HTTPException(
            status_code=422,
            detail="Could not segment this document into clauses. The file may be too short or unstructured.",
        )

    # Add plain-English simplified text to each clause
    clauses = simplify_all_clauses(clauses)

    # Hybrid risk flagging (rules + InLegalBERT)
    try:
        flagged = flag_all_clauses_hybrid(clauses)
    except Exception as e:
        logger.error(f"Hybrid flagging failed, falling back to rules only: {e}", exc_info=True)
        from backend.services.risk_flagger import flag_all_clauses
        flagged = flag_all_clauses(clauses)

    summary = get_risk_summary(flagged)

    # Save clause-level results
    saved_clauses = []
    for c in flagged:
        clause_row = Clause(
            document_id     = doc.id,
            clause_number   = c.get("number"),
            original_text   = c.get("text", ""),
            simplified_text = c.get("simplified_text"),
            clause_type     = c.get("bert_clause_type") or c.get("clause_type"),
            risk_level      = c.get("risk_level"),
            risk_reason     = c.get("risk_reason"),
            risk_tip        = c.get("risk_tip"),
            confidence      = c.get("confidence"),
        )
        db.add(clause_row)
        saved_clauses.append(clause_row)

    # Mark document as analysed and wipe raw text (privacy-first)
    doc.analysed_at    = datetime.utcnow()
    doc.raw_text        = None
    doc.raw_text_wiped  = True

    db.commit()
    for c in saved_clauses:
        db.refresh(c)

    logger.info(
        f"Document {doc.id} analysed: {len(flagged)} clauses, "
        f"overall_risk={summary['overall_risk']}"
    )

    return {
        "document_id": doc.id,
        "filename":    doc.filename,
        "summary":     summary,
        "clauses": [
            {
                "id":              c.id,
                "clause_number":   c.clause_number,
                "original_text":   c.original_text,
                "simplified_text": c.simplified_text,
                "clause_type":     c.clause_type,
                "risk_level":      c.risk_level,
                "risk_reason":     c.risk_reason,
                "risk_tip":        c.risk_tip,
                "confidence":      c.confidence,
            }
            for c in saved_clauses
        ],
    }


@router.get("/{document_id}", summary="Get previously analysed results for a document")
async def get_analysis(document_id: int, db: Session = Depends(get_db)):
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
                "id":              c.id,
                "clause_number":   c.clause_number,
                "original_text":   c.original_text,
                "simplified_text": c.simplified_text,
                "clause_type":     c.clause_type,
                "risk_level":      c.risk_level,
                "risk_reason":     c.risk_reason,
                "risk_tip":        c.risk_tip,
                "confidence":      c.confidence,
            }
            for c in clauses
        ],
    }