"""Document analysis endpoints with privacy-preserving result storage."""
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from backend.models.database import REDACTED_CLAUSE_TEXT, Clause, Document, get_db, wipe_expired_documents
from backend.services.clause_segmenter import segment_clauses
from backend.services.document_access import require_document_access
from backend.services.risk_flagger import flag_all_clauses, flag_all_clauses_hybrid, get_risk_summary
from backend.services.simplifier import simplify_all_clauses

logger = logging.getLogger("adharaai")
router = APIRouter()


@router.post("/{document_id}", summary="Run AI analysis on an uploaded document")
def analyze_document(
    document_id: int,
    document_token: str | None = Header(default=None, alias="X-Document-Token"),
    db: Session = Depends(get_db),
):
    require_document_access(document_id, document_token)
    wipe_expired_documents(db)

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found.")
    if doc.raw_text_wiped or not doc.raw_text:
        raise HTTPException(
            status_code=410,
            detail="This document's raw text has been automatically deleted for privacy. Please re-upload the file to analyse it again.",
        )

    clauses = segment_clauses(doc.raw_text)
    if not clauses:
        raise HTTPException(
            status_code=422,
            detail="Could not detect individual clauses in this document. Try uploading a cleaner copy or a text (.txt) version.",
        )

    clauses = simplify_all_clauses(clauses)
    try:
        flagged = flag_all_clauses_hybrid(clauses)
    except Exception:
        logger.exception("Hybrid flagging failed; falling back to rules only")
        flagged = flag_all_clauses(clauses)

    db.query(Clause).filter(Clause.document_id == document_id).delete()
    for clause in flagged:
        db.add(
            Clause(
                document_id=document_id,
                clause_number=clause["number"],
                # Do not retain uploaded source text after analysis.
                original_text=REDACTED_CLAUSE_TEXT,
                simplified_text=clause.get("simplified_text"),
                clause_type=clause.get("bert_clause_type") or clause.get("clause_type"),
                risk_level=clause.get("risk_level", "low"),
                risk_reason=clause.get("risk_reason"),
                risk_tip=clause.get("risk_tip"),
                confidence=clause.get("confidence", 100),
            )
        )

    doc.raw_text = None
    doc.raw_text_wiped = True
    doc.analysed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    summary = get_risk_summary(flagged)
    logger.info("Analysed document %s: %s clauses, high=%s", document_id, len(flagged), summary["high_risk"])
    return {
        **summary,
        "document_id": document_id,
        "filename": doc.filename,
        "clauses": [
            {
                "number": clause["number"],
                "original": clause["text"],
                "simplified": clause.get("simplified_text"),
                "risk_level": clause.get("risk_level", "low"),
                "risk_reason": clause.get("risk_reason"),
                "risk_tip": clause.get("risk_tip"),
                "confidence": clause.get("confidence", 100),
                "all_flags": clause.get("all_flags", []),
            }
            for clause in flagged
        ],
    }


@router.get("/{document_id}", summary="Retrieve a previously saved analysis")
def get_analysis(
    document_id: int,
    document_token: str | None = Header(default=None, alias="X-Document-Token"),
    db: Session = Depends(get_db),
):
    require_document_access(document_id, document_token)
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    clauses = db.query(Clause).filter(Clause.document_id == document_id).order_by(Clause.clause_number).all()
    if not clauses:
        raise HTTPException(status_code=404, detail="No analysis found for this document. Run POST /api/analyze/{id} first.")

    return {
        "document_id": document_id,
        "filename": doc.filename,
        "analysed_at": doc.analysed_at.isoformat() if doc.analysed_at else None,
        "clauses": [
            {
                "number": clause.clause_number,
                "original": None,
                "simplified": clause.simplified_text,
                "risk_level": clause.risk_level,
                "risk_reason": clause.risk_reason,
                "risk_tip": clause.risk_tip,
                "confidence": clause.confidence,
            }
            for clause in clauses
        ],
    }
