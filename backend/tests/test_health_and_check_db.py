import subprocess
import sys
import os
import pytest
from fastapi.testclient import TestClient
from backend.main import app

def test_api_health_endpoint():
    with TestClient(app) as client:
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "database" in data
        assert "dialect" in data["database"]
        assert "name" in data["database"]
        assert "connected" in data["database"]
        assert "migration_head" in data["database"]
        assert data["database"]["connected"] is True

def test_check_db_script():
    env = os.environ.copy()
    res = subprocess.run(
        [sys.executable, "scripts/check_db.py"],
        capture_output=True,
        text=True,
        env=env
    )
    assert res.returncode == 0
    stdout = res.stdout
    assert "Dialect:" in stdout
    assert "Host:" in stdout
    assert "Database:" in stdout
    assert "Alembic:" in stdout
    assert "Counts:" in stdout
    assert "Status:   OK" in stdout
    # Ensure no secrets leak in output
    assert "password" not in stdout.lower()
