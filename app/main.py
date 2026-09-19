import os
from typing import Annotated

import duckdb
import pydantic
from fastapi import Depends, FastAPI

from agents.f1_agent import run_f1_agent
from app.auth import get_current_player_id
from app.auth import router as auth_router

app = FastAPI(title="F1 Fantasy Agent API")
app.include_router(auth_router)


def get_db():
    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'f1_fantasy.db')
    con = duckdb.connect(db_path)
    try:
        yield con
    finally:
        con.close()


PlayerIdDep = Annotated[str, Depends(get_current_player_id)]
DbDep = Annotated[duckdb.DuckDBPyConnection, Depends(get_db)]


class RosterEntity(pydantic.BaseModel):
    entity_id: str
    name: str
    entity_type: str
    current_price: float


class RosterResponse(pydantic.BaseModel):
    player_id: str
    budget: float
    roster: list[RosterEntity]


@app.get("/roster/me", response_model=RosterResponse, description="User current player roster")
def get_my_roster(player_id: PlayerIdDep, db: DbDep):
    player_res = db.execute("SELECT budget FROM players WHERE player_id = ?", [player_id]).fetchone()
    if not player_res:
        # Auto-create player for demo simplicity if they came from Supabase
        db.execute("INSERT INTO players VALUES (?, 'new_manager', 100.00)", [player_id])
        player_res = (100.00,)
        
    budget = player_res[0]

    query = """
        SELECT r.entity_id, d.name, r.entity_type, d.current_price
        FROM rosters r
        JOIN drivers d ON r.entity_id = d.driver_id
        WHERE r.player_id = ? AND r.entity_type = 'driver'

        UNION ALL

        SELECT r.entity_id, c.name, r.entity_type, c.current_price
        FROM rosters r
        JOIN constructors c ON r.entity_id = c.constructor_id
        WHERE r.player_id = ? AND r.entity_type = 'constructor'
    """
    roster_res = db.execute(query, [player_id, player_id]).fetchall()

    return RosterResponse(
        player_id=player_id,
        budget=budget,
        roster=[
            RosterEntity(entity_id=row[0], name=row[1], entity_type=row[2], current_price=row[3])
            for row in roster_res
        ],
    )

class ChatRequest(pydantic.BaseModel):

    prompt: str

class ChatResponse(pydantic.BaseModel):
    answer: str
    cost_log: dict

@app.post("/chat", response_model=ChatResponse, description="Chat with the F1 Fantasy Agent")
def chat_with_agent(req: ChatRequest, player_id: PlayerIdDep, db: DbDep):
    result = run_f1_agent(req.prompt, player_id, db)
    return ChatResponse(answer=result["answer"], cost_log=result["cost_log"])
