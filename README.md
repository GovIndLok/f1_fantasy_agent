# F1 Fantasy Agent - Your 10x Solution

## What is this?
An objective, conversational AI analyst for F1 Fantasy players. It helps managers evaluate multi-week scenarios and make mathematically sound transfer decisions, eliminating emotional bias.

## The 5 Concepts
| Concept | Where it lives in the code |
|---------|----------------------------|
| **1. API Endpoints** | `app/main.py`, `app/auth/router.py`, `app/rosters/router.py` |
| **2. Database** | `app/database.py` (schema and connections) · `app/f1_data.py` (seed and sync CLI) |
| **3. Authentication** | `app/auth/utils.py` (Supabase client + JWT) · `app/auth/router.py` (endpoints) |
| **4. LLM Integration** | `agents/f1_analyst/agent.py` (LangChain + Gemini assembly) |
| **5. Agent with guardrails (Swap)** | `agents/f1_analyst/agent.py` (system prompt) · `agents/f1_analyst/tools.py` (DB-bound tools) |

## Setup & Run Instructions

**1. Clone and Install dependencies**
This project uses `uv` for dependency management.
```bash
uv sync
```

### Testing
We use `pytest` for running automated tests. To execute tests for the SQL Agent and other components:
```bash
uv run pytest
```

**2. Environment Variables**
Create a `.env` file in the project root with the following:
```env
GEMINI_API_KEY="your-gemini-api-key"
SUPABASE_URL="your-supabase-url"
SUPABASE_KEY="your-supabase-anon-key"
```

**3. Seed the Database**
Rebuild the historical F1 statistics database for 2023–2025. Player and roster data are preserved:
```bash
uv run python -m app.f1_data seed
```

To add eligible races from the current season:
```bash
uv run python -m app.f1_data sync
```

**4. Start the Server**
```bash
uv run uvicorn app.main:app --reload --env-file .env
```

## 5-Minute Demo Path

0. **Check API Status**
```bash
curl -X GET http://127.0.0.1:8000/status
```

1. **Register a test user**
```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

2. **Login and get a token**
```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```
*(Copy the `access_token` from the response)*

3. **Check your Roster (Requires Token)**
```bash
curl -X GET http://127.0.0.1:8000/roster/me \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
```

4. **Chat with the Agent (Requires Token)**
Ask the agent about F1 Fantasy decisions. It will refuse to answer non-F1 questions (guardrails).
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Should I add Max Verstappen to my roster?"}'
```
