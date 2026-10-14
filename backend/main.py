"""
FastAPI application entrypoint.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routers import snapshots, analytics, opportunities, ai, export, insights, health, admin_auth
from backend.routers import v2_overview, v2_expiry, v2_approvals, v2_business_units, v2_regions, v2_delayed, v2_filters, v2_explorer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting up...")
    from backend.database import engine
    dialect = getattr(engine.dialect, "name", "sqlite")
    is_postgres = dialect == "postgresql"
    try:
        from alembic.config import Config
        from alembic import command
        from pathlib import Path
        alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
        log.info("Applying database migrations (alembic upgrade head)...")
        command.upgrade(alembic_cfg, "head")
        log.info("Database migrations applied successfully.")
        migrations_status = "migrations at head"
    except Exception as e:
        log.error("Alembic upgrade failed on startup: %s", e)
        if is_postgres:
            log.critical("FATAL: Database migration failed on PostgreSQL. Halting startup.")
            raise RuntimeError(f"Database migration failed on PostgreSQL: {e}") from e
        else:
            log.warning("Falling back to Base.metadata.create_all on SQLite (%s)...", e)
            from backend.database import Base
            Base.metadata.create_all(bind=engine)
            migrations_status = "fallback to create_all"

    # Startup log: on boot, log one line such as Database: postgresql @ localhost:5432/renewals (migrations at head).
    try:
        from urllib.parse import urlparse
        db_url_parsed = urlparse(settings.DATABASE_URL)
        if dialect == "sqlite":
            db_target = db_url_parsed.path or settings.DATABASE_URL.replace("sqlite:///", "")
            log.info(f"Database: sqlite @ {db_target} ({migrations_status})")
        else:
            host = db_url_parsed.hostname or "localhost"
            port = db_url_parsed.port or 5432
            dbname = db_url_parsed.path.lstrip("/")
            log.info(f"Database: {dialect} @ {host}:{port}/{dbname} ({migrations_status})")
    except Exception as log_err:
        log.info(f"Database: {dialect} ({migrations_status})")

    yield
    log.info("Shutting down.")


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(snapshots.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(opportunities.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(insights.router, prefix="/api")
app.include_router(health.router)
app.include_router(admin_auth.router, prefix="/api")
app.include_router(admin_auth.router)
app.include_router(v2_overview.router)
app.include_router(v2_expiry.router)
app.include_router(v2_approvals.router)
app.include_router(v2_business_units.router)  # has its own /api/v2/overview prefix
app.include_router(v2_regions.router)
app.include_router(v2_delayed.router)
app.include_router(v2_filters.router)
app.include_router(v2_explorer.router, prefix="/api")
app.include_router(v2_explorer.router)

# Direct routes without /api prefix
app.include_router(snapshots.router)
app.include_router(analytics.router)
app.include_router(opportunities.router)
app.include_router(ai.router)
app.include_router(export.router)
app.include_router(insights.router)


# Top-level direct routes matching specification
from fastapi import Query, Form, File, UploadFile, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database import get_db
from backend.services.context import UserContext, get_user_context

@app.get("/compare", tags=["analytics"])
@app.get("/api/compare", tags=["analytics"])
def compare_direct(
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    scope: str = Query("renewals"),
    include_deleted_lost: bool = Query(False),
    db: Session = Depends(get_db),
    ctx: UserContext = Depends(get_user_context),
):
    from backend.routers.analytics import compare_dates
    from backend.services.analytics_service import AnalyticsService
    return compare_dates(from_date=from_date, to_date=to_date, scope=scope, include_deleted_lost=include_deleted_lost, svc=AnalyticsService(db), ctx=ctx)

@app.get("/snapshots", tags=["snapshots"])
def snapshots_direct(db: Session = Depends(get_db), ctx: UserContext = Depends(get_user_context)):
    from backend.routers.snapshots import list_snapshots
    return list_snapshots(db=db, ctx=ctx)



@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    dialect = "unknown"
    db_name = "unknown"
    connected = False
    migration_head = False

    try:
        from urllib.parse import urlparse
        parsed = urlparse(settings.DATABASE_URL)
        dialect = getattr(db.bind.dialect, "name", "unknown")
        db_name = parsed.path.lstrip("/") if parsed.path else ("local" if dialect == "sqlite" else "unknown")
        
        # Test connection
        db.execute(text("SELECT 1"))
        connected = True

        # Check migration head
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext
        from pathlib import Path

        alembic_ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
        if alembic_ini_path.exists():
            alembic_cfg = Config(str(alembic_ini_path))
            script = ScriptDirectory.from_config(alembic_cfg)
            head_rev = script.get_current_head()
            conn = db.connection()
            ctx = MigrationContext.configure(conn)
            current_rev = ctx.get_current_revision()
            migration_head = (current_rev == head_rev)
    except Exception:
        connected = False

    return {
        "status": "ok" if connected else "error",
        "version": settings.APP_VERSION,
        "database": {
            "dialect": dialect,
            "name": db_name,
            "connected": connected,
            "migration_head": migration_head,
        },
    }


# Serve frontend static files in production (when dist/ exists)
import os
dist_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(dist_path):
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="frontend")
