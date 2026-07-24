from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.models.database import Document, Clause, get_db

router = APIRouter()

@router.get("/", summary="List all uploaded documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return [
        {
            "id":           d.id,
            "filename":     d.filename,
            "created_at":   d.created_at.isoformat(),
            "analysed":     d.analysed_at is not None,
            "raw_wiped":    d.raw_text_wiped,
            "clause_count": db.query(Clause).filter(Clause.document_id == d.id).count(),
        }
        for d in docs
    ]

@router.delete("/{document_id}", summary="Delete a document and all its clause data")
def delete_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    db.query(Clause).filter(Clause.document_id == document_id).delete()
    db.delete(doc)
    db.commit()
    return {"message": f"Document {document_id} and all associated data deleted."}
