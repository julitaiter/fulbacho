from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.groups.models import GroupRole


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class GroupUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class GroupJoin(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    code: str
    created_by_id: UUID
    created_at: datetime


class MemberOut(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    display_name: str
    role: GroupRole
    joined_at: datetime


class MemberRoleUpdate(BaseModel):
    role: GroupRole


class GroupOverview(GroupOut):
    players_count: int
    matches_count: int
    role: GroupRole
