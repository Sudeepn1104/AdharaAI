from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.models.database import get_db
from config import settings
import psutil, datetime

router = APIRouter()

@router.get("/", summary="Health check — used by Render and uptime monitors")
def health(db: Session = Depends(get_db)):
    # Quick DB ping
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status":    "ok" if db_ok else "degraded",
        "version":   settings.APP_VERSION,
        "env":       settings.APP_ENV,
        "db":        "ok" if db_ok else "error",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "memory_mb": round(psutil.Process().memory_info().rss / 1024 / 1024, 1),
    }
