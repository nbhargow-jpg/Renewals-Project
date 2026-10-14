import asyncio
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.main import lifespan, app
from backend.database import get_db

def test_startup_fails_fast_on_broken_postgres_migration():
    async def _run():
        with patch("backend.database.engine") as mock_engine, \
             patch("alembic.command.upgrade", side_effect=Exception("PostgreSQL migration 0002 failed")):
            mock_engine.dialect.name = "postgresql"
            with pytest.raises(RuntimeError, match="Database migration failed on PostgreSQL"):
                async with lifespan(app):
                    pass
    asyncio.run(_run())

def test_startup_falls_back_on_sqlite_migration_failure():
    async def _run():
        with patch("backend.database.engine") as mock_engine, \
             patch("backend.database.Base.metadata.create_all") as mock_create_all, \
             patch("alembic.command.upgrade", side_effect=Exception("SQLite migration error")):
            mock_engine.dialect.name = "sqlite"
            async with lifespan(app):
                pass
            mock_create_all.assert_called_once()
    asyncio.run(_run())

def test_db_health_reports_dialect_and_alembic(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        res = client.get("/api/health/db")
        assert res.status_code == 200
        data = res.json()
        assert "dialect" in data
        assert "alembic_revision" in data
        assert "alembic_head" in data
        assert data["status"] in ["ok", "error"]
    finally:
        app.dependency_overrides.clear()

def test_db_health_reports_error_when_unreachable():
    mock_db = MagicMock()
    mock_db.execute.side_effect = Exception("Connection refused to database")
    mock_db.bind.dialect.name = "postgresql"
    
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        client = TestClient(app)
        res = client.get("/api/health/db")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "error"
        assert "Connection refused" in data["error"]
        assert data["dialect"] == "postgresql"
    finally:
        app.dependency_overrides.clear()
