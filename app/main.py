from typing import Annotated

from fastapi import Depends, FastAPI

from agents.f1_analyst import run_f1_agent
from agents.f1_analyst.schema import ChatRequest, ChatResponse
from app.auth import get_current_player_id
from app.auth import router as auth_router
from app.database import DbDep
from app.rosters import router as roster_router

app = FastAPI(title="F1 Fantasy Agent API")
app.include_router(auth_router)
app.include_router(roster_router)

PlayerIdDep = Annotated[str, Depends(get_current_player_id)]


@app.get("/status", tags=["system"], description="Get API status")
@app.get("/", tags=["system"], include_in_schema=False)
def get_status(db: DbDep):
    db_status = "connected"
    try:
        db.execute("SELECT 1").fetchone()
    except Exception as e:
        db_status = f"unavailable: {e}"

    return {
        "status": "operational",
        "api_version": "0.1.0",
        "database": db_status,
        "message": "F1 Fantasy Agent API is running",
    }


@app.post("/chat", response_model=ChatResponse, description="Chat with the F1 Fantasy Agent")
def chat_with_agent(req: ChatRequest, player_id: PlayerIdDep, db: DbDep):
    result = run_f1_agent(req.prompt, player_id, db)
    return ChatResponse(answer=result["answer"], cost_log=result["cost_log"])
