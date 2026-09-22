from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth import get_current_player_id
from app.database import DbDep
from app.rosters.schema import RosterEntity, RosterResponse

router = APIRouter(tags=["rosters"])

PlayerIdDep = Annotated[str, Depends(get_current_player_id)]


@router.get("/roster/me", response_model=RosterResponse, description="User's current F1 Fantasy roster")
def get_my_roster(player_id: PlayerIdDep, db: DbDep):
    player_res = db.execute(
        "SELECT player_id FROM players WHERE player_id = ?", [player_id]
    ).fetchone()
    if not player_res:
        db.execute("INSERT INTO players VALUES (?, 'new_manager')", [player_id])

    query = """
        SELECT r.entity_id, d.name, r.entity_type
        FROM rosters r
        JOIN stats.drivers d ON r.entity_id = d.driver_id
        WHERE r.player_id = ? AND r.entity_type = 'driver'

        UNION ALL

        SELECT r.entity_id, c.name, r.entity_type
        FROM rosters r
        JOIN stats.constructors c ON r.entity_id = c.constructor_id
        WHERE r.player_id = ? AND r.entity_type = 'constructor'
    """
    roster_res = db.execute(query, [player_id, player_id]).fetchall()

    return RosterResponse(
        player_id=player_id,
        roster=[
            RosterEntity(entity_id=row[0], name=row[1], entity_type=row[2])
            for row in roster_res
        ],
    )

