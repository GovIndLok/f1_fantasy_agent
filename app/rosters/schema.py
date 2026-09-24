from pydantic import BaseModel, Field


class RosterEntity(BaseModel):
    entity_id: str
    name: str
    entity_type: str


class RosterResponse(BaseModel):
    player_id: str
    roster: list[RosterEntity]


class RosterTransferRequest(BaseModel):
    remove: list[str] = Field(default_factory=list)
    add: list[str] = Field(default_factory=list)
