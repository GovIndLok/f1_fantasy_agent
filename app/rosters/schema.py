from pydantic import BaseModel


class RosterEntity(BaseModel):
    entity_id: str
    name: str
    entity_type: str


class RosterResponse(BaseModel):
    player_id: str
    roster: list[RosterEntity]


