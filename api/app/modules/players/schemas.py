from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlayerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    linked_user_id: UUID | None = None


class PlayerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    linked_user_id: UUID | None = None
    active: bool | None = None


class PlayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    group_id: UUID
    name: str
    linked_user_id: UUID | None
    active: bool
    created_at: datetime


class CasualParticipantOut(BaseModel):
    id: UUID
    match_id: UUID
    match_played_at: datetime
    display_name: str
    team: str


class PromoteCasualRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    participant_ids: list[UUID] = Field(min_length=1)
    linked_user_id: UUID | None = None


class AttachCasualRequest(BaseModel):
    participant_ids: list[UUID] = Field(min_length=1)
