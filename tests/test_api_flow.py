import uuid
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.auth.utils import get_supabase
from app.main import app


# Mock Supabase to bypass Python 3.14 SSL context crashes in the test sandbox
class MockUser:
    def __init__(self):
        self.id = "user_1" # Match the player_id in our duckdb seed
class MockSession:
    def __init__(self):
        self.access_token = "mock_jwt_token"
class MockAuthResponse:
    def __init__(self):
        self.user = MockUser()
        self.session = MockSession()

mock_supabase = MagicMock()
mock_supabase.auth.sign_up.return_value = MockAuthResponse()
mock_supabase.auth.sign_in_with_password.return_value = MockAuthResponse()
mock_supabase.auth.get_user.return_value = MockAuthResponse()

app.dependency_overrides[get_supabase] = lambda: mock_supabase

client = TestClient(app)

# Global state to share between sequential tests
# This simulates a real user's session flow
state = {}

def test_0_api_status():
    """Test the API status endpoints."""
    # Test /status
    res = client.get("/status")
    assert res.status_code == 200, f"Status check failed: {res.text}"
    data = res.json()
    assert data["status"] == "operational"
    assert data["database"] == "connected"
    assert "api_version" in data

    # Test root /
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "operational"

def test_1_register_user():
    """Test creating a new test user via the API."""
    state["email"] = f"test_{uuid.uuid4().hex[:8]}@example.com"
    state["password"] = "TestSecurePassword123!"
    
    res = client.post(
        "/auth/register",
        json={"email": state["email"], "password": state["password"]}
    )
    
    assert res.status_code == 200, f"Registration failed: {res.text}"
    data = res.json()
    assert "user" in data

def test_2_login_user():
    """Test logging in with the newly created user credentials."""
    res = client.post(
        "/auth/login",
        json={"email": state["email"], "password": state["password"]}
    )
    
    assert res.status_code == 200, f"Login failed: {res.text}"
    data = res.json()
    assert "access_token" in data
    
    # Store token for subsequent requests
    state["token"] = data["access_token"]

def test_3_get_roster():
    """Test fetching the user's roster using their access token."""
    headers = {"Authorization": f"Bearer {state['token']}"}
    res = client.get("/roster/me", headers=headers)
    
    assert res.status_code == 200, f"Roster fetch failed: {res.text}"
    data = res.json()
    assert "player_id" in data
    assert "roster" in data
    
    # The seed_db script creates 7 entities (5 drivers, 2 constructors) for user_1
    assert len(data["roster"]) == 7

def test_4_chat_with_agent():
    """Test the main F1 Analyst agent's ability to answer an F1 query."""
    headers = {"Authorization": f"Bearer {state['token']}"}
    payload = {"prompt": "Who won the 2024 Bahrain Grand Prix?"}
    
    res = client.post("/chat", headers=headers, json=payload)
    
    assert res.status_code == 200, f"Chat failed: {res.text}"
    data = res.json()
    
    # Verify the structure of the response
    assert "answer" in data
    
    # Verify the agent used its SQL tools and correctly answered the question
    answer_lower = data["answer"].lower()
    assert "verstappen" in answer_lower
