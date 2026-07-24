"""
database.py — SQLAlchemy models with privacy-first design.

Key privacy decision:
  Raw document text is stored ONLY during analysis.
  After DOCUMENT_TTL seconds (default 5 min), raw_text is wiped.
  We keep only clause-level results — never the full original document.

Database:
  Development  → SQLite (zero config)
  Production   → PostgreSQL (set DATABASE_URL in .env)
"""
from sqlalchemy import (
    create_engine, Column, Integer, String, Text,
    DateTime, Boolean, event
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from config import settings

# ── Engine ──────────────────────────────────────────────────────────────────

connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


# ── Models ───────────────────────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id              = Column(Integer, primary_key=True, index=True)
    filename        = Column(String(255), nullable=False)

    # raw_text is TEMPORARY — wiped after analysis or after TTL expires
    # Never expose this field in API responses
    raw_text        = Column(Text, nullable=True)
    raw_text_wiped  = Column(Boolean, default=False)

    doc_type        = Column(String(100), nullable=True)
    char_count      = Column(Integer, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    analysed_at     = Column(DateTime, nullable=True)
    expires_at      = Column(DateTime, nullable=True)  # when raw_text gets wiped


class Clause(Base):
    __tablename__ = "clauses"

    id              = Column(Integer, primary_key=True, index=True)
    document_id     = Column(Integer, nullable=False, index=True)
    clause_number   = Column(Integer, nullable=True)
    original_text   = Column(Text, nullable=False)
    simplified_text = Column(Text, nullable=True)
    clause_type     = Column(String(100), nullable=True)
    risk_level      = Column(String(20), nullable=True)
    risk_reason     = Column(Text, nullable=True)
    risk_tip        = Column(Text, nullable=True)
    confidence      = Column(Integer, nullable=True)   # 0-100


# ── Init & helpers ────────────────────────────────────────────────────────────

def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def wipe_expired_documents(db):
    """
    Auto-delete raw_text from documents past their TTL.
    Called at the start of each /analyze and /upload request.
    """
    now = datetime.utcnow()
    expired = db.query(Document).filter(
        Document.expires_at <= now,
        Document.raw_text_wiped == False,
        Document.raw_text != None
    ).all()
    for doc in expired:
        doc.raw_text = None
        doc.raw_text_wiped = True
    if expired:
        db.commit()
    return len(expired)
