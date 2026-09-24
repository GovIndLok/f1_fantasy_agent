from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth.utils import get_current_player_id
from app.database import DbDep
from app.rosters.schema import RosterEntity, RosterResponse, RosterTransferRequest
from app.rosters.service import get_roster, transfer_roster_entities

router = APIRouter(tags=["rosters"])

PlayerIdDep = Annotated[str, Depends(get_current_player_id)]


@router.get("/roster/me", response_model=RosterResponse, description="User's current F1 Fantasy roster")
def get_my_roster(player_id: PlayerIdDep, db: DbDep):
    return RosterResponse(
        player_id=player_id,
        roster=[RosterEntity(**entity) for entity in get_roster(player_id, db)],
    )


@router.post("/roster/transfer", description="Make a driver or constructor transfer")
def transfer_roster(req: RosterTransferRequest, player_id: PlayerIdDep, db: DbDep):
    try:
        return transfer_roster_entities(player_id, req.remove, req.add, db)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
