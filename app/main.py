import logging
import threading
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from agents.f1_analyst.agent import run_f1_agent
from app.auth.router import router as auth_router
from app.auth.utils import get_current_player_id
from app.database import DbDep
from app.f1_data import sync_current_season
from app.rosters.router import router as roster_router

_sync_ready = threading.Event()
_sync_error: str | None = None


def _run_startup_sync() -> None:
    global _sync_error
    try:
        count = sync_current_season()
        logging.info("Startup sync complete: %d new race(s) stored.", count)
        _sync_error = None
    except Exception as exc:
        logging.exception("Startup sync failed.")
        _sync_error = str(exc)
    finally:
        _sync_ready.set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    thread = threading.Thread(target=_run_startup_sync, daemon=True, name="startup-sync")
    thread.start()
    yield


class ChatRequest(BaseModel):
    prompt: str


class ChatResponse(BaseModel):
    answer: str
    cost_log: dict


app = FastAPI(title="F1 Fantasy Agent API", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(roster_router)

PlayerIdDep = Annotated[str, Depends(get_current_player_id)]


@app.get("/status", tags=["system"], description="Get API status")
@app.get("/", tags=["system"], include_in_schema=False)
def get_status(db: DbDep):
    db_status = "connected"
    try:
        db.execute("SELECT 1").fetchone()
    except Exception as exc:
        db_status = f"unavailable: {exc}"

    ready = _sync_ready.is_set()
    if not ready:
        sync_status = "running"
    elif _sync_error:
        sync_status = f"failed: {_sync_error}"
    else:
        sync_status = "ok"

    return {
        "status": "operational" if ready else "starting",
        "ready": ready,
        "api_version": "0.1.0",
        "database": db_status,
        "sync": sync_status,
        "message": "F1 Fantasy Agent API is running",
    }


@app.post("/chat", response_model=ChatResponse, description="Chat with the F1 Fantasy Agent")
def chat_with_agent(req: ChatRequest, player_id: PlayerIdDep, db: DbDep):
    result = run_f1_agent(req.prompt, player_id, db)
    return ChatResponse(answer=result["answer"], cost_log=result["cost_log"])
