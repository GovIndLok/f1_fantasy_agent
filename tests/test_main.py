import duckdb
import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.database import get_db
from app.main import app


@pytest.fixture(autouse=True)
def reset_sync_state():
    """Isolate _sync_ready and _sync_error between tests."""
    main_module._sync_ready.clear()
    main_module._sync_error = None
    yield
    main_module._sync_ready.clear()
    main_module._sync_error = None


@pytest.fixture()
def client():
    db = duckdb.connect(":memory:")
    app.dependency_overrides[get_db] = lambda: db
    test_client = TestClient(app)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()
    db.close()


def test_status_while_sync_running(client):
    """_sync_ready not set → server reports starting / not ready."""
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is False
    assert data["status"] == "starting"
    assert data["sync"] == "running"


def test_status_after_sync_success(client):
    """_sync_ready set, no error → server reports operational / ready."""
    main_module._sync_ready.set()
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["status"] == "operational"
    assert data["sync"] == "ok"


def test_status_after_sync_failure(client):
    """_sync_ready set after failure → server stays up; sync field reports error."""
    main_module._sync_ready.set()
    main_module._sync_error = "network error"
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["status"] == "operational"
    assert data["sync"] == "failed: network error"

