"""
conftest.py — shared fixtures for all tests.
Loads the real Oct-5 data files into an in-memory SQLite DB.
"""
import pytest
from datetime import date
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.services.context import ADMIN_CONTEXT
from backend.services.ingest_service import IngestService
from backend.config import settings

DATA_DIR = settings.DATA_DIR
RENEWALS_FILE = DATA_DIR / "Renewals Summary 3.xlsx"
COMPARISON_FILE = DATA_DIR / "Renewal Comparison Tool 11.xlsx"
SNAPSHOT_DATE = date(2026, 10, 5)   # Oct 5 reference date


from sqlalchemy.pool import StaticPool
import os


@pytest.fixture(scope="session", autouse=True)
def setup_test_admin_auth():
    old_pw = settings.ADMIN_PASSWORD
    old_key = settings.ADMIN_SECRET_KEY
    if not settings.ADMIN_PASSWORD:
        settings.ADMIN_PASSWORD = "test-admin-secret-password-xyz"
    if not settings.ADMIN_SECRET_KEY:
        settings.ADMIN_SECRET_KEY = "test-secret-key-32bytes-hex-dummy-value"
    yield
    settings.ADMIN_PASSWORD = old_pw
    settings.ADMIN_SECRET_KEY = old_key


@pytest.fixture(scope="session")
def db_engine():
    test_db_url = os.environ.get("TEST_DATABASE_URL")
    if test_db_url:
        if test_db_url.startswith("postgres://"):
            test_db_url = test_db_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif test_db_url.startswith("postgresql://") and not test_db_url.startswith("postgresql+"):
            test_db_url = test_db_url.replace("postgresql://", "postgresql+psycopg://", 1)
        engine = create_engine(test_db_url, pool_pre_ping=True)
    else:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="session")
def seeded_session(db_session):
    """
    Load both Excel files into the in-memory DB exactly once for all tests.
    """
    svc = IngestService(db_session)
    svc.ingest_renewals_summary(
        ADMIN_CONTEXT,
        RENEWALS_FILE,
        snapshot_date=SNAPSHOT_DATE,
        label="Today",
    )
    if COMPARISON_FILE.exists():
        snap = (
            db_session.query(__import__("backend.models.snapshot", fromlist=["UploadSnapshot"]).UploadSnapshot)
            .filter_by(is_active_today=True)
            .first()
        )
        if snap:
            svc.ingest_comparison_tool(ADMIN_CONTEXT, COMPARISON_FILE, snap)
    db_session.commit()
    return db_session

