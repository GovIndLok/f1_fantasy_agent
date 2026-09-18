import typing

import duckdb
import pydantic
from fastapi import Depends, FastAPI, HTTPException

app = FastAPI(title="F1 Fantasy Agent API")

def get_db():
    con = duckdb.connect('../data/f1_fantasy.db')
    try:
        yield con
    finally:
        con.close()

# Dummy auth dependency for M2 Walking Skeleton.
# This will be replaced with real JWT auth in M3 (Concept #3).
def get_current_player_id():
    return "user_1"

class RosterEntity(pydantic.BaseModel):
    entity_id: str
    name: str
    entity_type: str
    current_price: float

class RosterResponse(pydantic.BaseModel):
    player_id: str
    budget: float
    roster: typing.List[RosterEntity]

@app.get("/roster/me", response_model=RosterResponse)
def get_my_roster(
    player_id: str = Depends(get_current_player_id),
    db: duckdb.DuckDBPyConnection = Depends(get_db)
):
    # Fetch player budget
    player_res = db.execute("SELECT budget FROM players WHERE player_id = ?", [player_id]).fetchone()
    if not player_res:
        raise HTTPException(status_code=404, detail="Player not found")
    budget = player_res[0]

    # Fetch roster details by joining with drivers and constructors
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
    
    roster_entities = [
        RosterEntity(entity_id=row[0], name=row[1], entity_type=row[2], current_price=row[3])
        for row in roster_res
    ]

    return RosterResponse(
        player_id=player_id,
        budget=budget,
        roster=roster_entities
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

