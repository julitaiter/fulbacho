from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.matches.models import TeamSide


class ParticipantInput(BaseModel):
    ref: str = Field(min_length=1, max_length=40)
    player_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def require_player_or_name(self):
        if self.player_id is None and not self.name:
            raise ValueError("Un casual requiere name")
        return self


class TeamInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    score: int = Field(ge=0)
    participants: list[ParticipantInput]


class GoalInput(BaseModel):
    participant_ref: str | None = None
    own_goal: bool = False
    team_scored_for: TeamSide | None = None

    @model_validator(mode="after")
    def validate_anonymous(self):
        if self.participant_ref is None and self.own_goal:
            raise ValueError("Un gol en contra no puede ser anónimo")
        if self.participant_ref is None and self.team_scored_for is None:
            raise ValueError("Un gol anónimo requiere team_scored_for")
        return self


class MatchCreate(BaseModel):
    played_at: datetime
    players_per_team: int = Field(ge=1, le=50)
    location: str | None = Field(default=None, max_length=200)
    team_a: TeamInput
    team_b: TeamInput
    goals: list[GoalInput] = Field(default_factory=list)


class MatchUpdate(MatchCreate):
    pass


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    player_id: UUID | None
    display_name: str
    team: TeamSide


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    participant_id: UUID | None
    own_goal: bool
    team_scored_for: TeamSide


class MatchOut(BaseModel):
    id: UUID
    group_id: UUID
    played_at: datetime
    players_per_team: int
    location: str | None
    team_a_name: str
    team_b_name: str
    score_a: int
    score_b: int
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    can_edit: bool
    participants: list[ParticipantOut]
    goals: list[GoalOut]
