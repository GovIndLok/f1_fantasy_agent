from types import SimpleNamespace

import duckdb
import pytest
from fastapi.testclient import TestClient

from app import main
from app.auth.utils import get_supabase
from app.database import create_players_schema, get_db
from app.main import app


class FakeAuth:
    def sign_up(self, credentials):
        return SimpleNamespace(user=SimpleNamespace(id="user_1", email=credentials["email"]))

    def sign_in_with_password(self, credentials):
        return SimpleNamespace(
            session=SimpleNamespace(access_token="mock_jwt_token")
        )

    def get_user(self, token):
        return SimpleNamespace(user=SimpleNamespace(id="user_1"))


@pytest.fixture()
def db():
    connection = duckdb.connect(":memory:")
    create_players_schema(connection)
    connection.execute("INSERT INTO players VALUES ('user_1', 'f1_fanatic')")
    connection.execute("ATTACH ':memory:' AS stats")
    connection.execute("CREATE TABLE stats.drivers (driver_id VARCHAR, name VARCHAR, code VARCHAR, nationality VARCHAR)")
    connection.execute("CREATE TABLE stats.constructors (constructor_id VARCHAR, name VARCHAR, nationality VARCHAR)")
    connection.executemany(
        "INSERT INTO stats.drivers VALUES (?, ?, ?, ?)",
        [
            ["driver_a", "Driver A", "A", "Test"],
            ["driver_b", "Driver B", "B", "Test"],
            ["driver_c", "Driver C", "C", "Test"],
            ["driver_d", "Driver D", "D", "Test"],
            ["driver_e", "Driver E", "E", "Test"],
            ["driver_f", "Driver F", "F", "Test"],
        ],
    )
    connection.executemany(
        "INSERT INTO stats.constructors VALUES (?, ?, ?)",
        [
            ["team_a", "Team A", "Test"],
            ["team_b", "Team B", "Test"],
            ["team_c", "Team C", "Test"],
        ],
    )
    connection.executemany(
        "INSERT INTO rosters VALUES ('user_1', ?, ?)",
        [
            ["driver_a", "driver"],
            ["driver_b", "driver"],
            ["driver_c", "driver"],
            ["driver_d", "driver"],
            ["driver_e", "driver"],
            ["team_a", "constructor"],
            ["team_b", "constructor"],
        ],
    )
    yield connection
    connection.close()


@pytest.fixture()
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_supabase] = lambda: SimpleNamespace(auth=FakeAuth())
    test_client = TestClient(app)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()


def auth_headers():
    return {"Authorization": "Bearer mock_jwt_token"}


def test_startup_does_not_start_background_sync():
    assert not hasattr(main, "start_background_sync")

    with TestClient(app):
        pass


def test_status_reports_connected_database(client):
    response = client.get("/status")

    assert response.status_code == 200
    assert response.json() == {
        "status": "operational",
        "api_version": "0.1.0",
        "database": "connected",
        "message": "F1 Fantasy Agent API is running",
    }


def test_auth_registration_and_login_preserve_envelopes(client):
    registration = client.post(
        "/auth/register",
        json={"email": "player@example.com", "password": "password"},
    )
    login = client.post(
        "/auth/login",
        json={"email": "player@example.com", "password": "password"},
    )

    assert registration.status_code == 200
    assert registration.json()["message"] == "User registered successfully"
    assert login.status_code == 200
    assert login.json() == {
        "access_token": "mock_jwt_token",
        "token_type": "bearer",
    }


def test_roster_endpoint_returns_the_service_roster(client):
    response = client.get("/roster/me", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["player_id"] == "user_1"
    assert len(response.json()["roster"]) == 7


def test_transfer_endpoint_persists_a_valid_swap(client):
    response = client.post(
        "/roster/transfer",
        headers=auth_headers(),
        json={"remove": ["driver_a"], "add": ["driver_f"]},
    )

    assert response.status_code == 200
    assert response.json()["transferred_out"] == ["driver_a"]
    assert response.json()["transferred_in"] == ["driver_f"]
    roster = client.get("/roster/me", headers=auth_headers()).json()["roster"]
    assert "driver_f" in {entity["entity_id"] for entity in roster}
    assert "driver_a" not in {entity["entity_id"] for entity in roster}


def test_transfer_endpoint_preserves_business_error_mapping(client):
    response = client.post(
        "/roster/transfer",
        headers=auth_headers(),
        json={"remove": ["driver_a"], "add": []},
    )

    assert response.status_code == 422
    assert "5 drivers" in response.json()["detail"]


def test_chat_route_preserves_response_envelope(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "run_f1_agent",
        lambda prompt, player_id, db: {
            "answer": "Check the historical data.",
            "cost_log": {"total_tokens": 4},
        },
    )

    response = client.post(
        "/chat",
        headers=auth_headers(),
        json={"prompt": "Who won Bahrain?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Check the historical data.",
        "cost_log": {"total_tokens": 4},
    }
