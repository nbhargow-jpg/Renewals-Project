from pathlib import Path
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from backend.database import get_db

router = APIRouter(prefix="/api/health", tags=["health"])

@router.get("/db")
def get_db_health(db: Session = Depends(get_db)):
    dialect = "unknown"
    try:
        dialect = getattr(db.bind.dialect, "name", "unknown")
        # Connectivity check
        db.execute(text("SELECT 1"))
        
        inspector = inspect(db.bind)
        table_names = inspector.get_table_names()
        cols = [c["name"] for c in inspector.get_columns("opportunities")] if "opportunities" in table_names else []
        is_legacy = ("fiscal_period" not in cols or "sales_type" not in cols) if cols else False
        
        # Alembic revision check
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext
        
        alembic_cfg = Config(str(Path(__file__).resolve().parent.parent.parent / "alembic.ini"))
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()
        
        conn = db.connection()
        context = MigrationContext.configure(conn)
        current_rev = context.get_current_revision()
        
        is_behind = (current_rev != head_rev)
        
        if is_behind:
            return {
                "status": "error",
                "dialect": dialect,
                "alembic_revision": current_rev,
                "alembic_head": head_rev,
                "is_legacy": is_legacy,
                "version": "v2" if not is_legacy else "v1",
                "error": f"Database schema revision ({current_rev}) is behind Alembic head ({head_rev})"
            }
            
        return {
            "status": "ok",
            "dialect": dialect,
            "alembic_revision": current_rev,
            "alembic_head": head_rev,
            "is_legacy": is_legacy,
            "version": "v2" if not is_legacy else "v1"
        }
    except Exception as e:
        return {
            "status": "error",
            "dialect": dialect,
            "alembic_revision": None,
            "alembic_head": None,
            "error": str(e)
        }
