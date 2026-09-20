from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from backend.models.database import Document, Clause, get_db
from backend.services.document_access import require_document_access

router = APIRouter()

@router.delete("/{document_id}", summary="Delete a document and all its clause data")
def delete_document(document_id: int, document_token: str | None = Header(default=None, alias="X-Document-Token"), db: Session = Depends(get_db)):
    require_document_access(document_id, document_token)
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    db.query(Clause).filter(Clause.document_id == document_id).delete()
    db.delete(doc)
    db.commit()
    return {"message": f"Document {document_id} and all associated data deleted."}
