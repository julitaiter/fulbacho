from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MatchBrief(BaseModel):
    id: UUID
    played_at: datetime
    team_a_name: str
    team_b_name: str
    score_a: int
    score_b: int


class GroupSummary(BaseModel):
    total_matches: int
    total_goals: int
    total_own_goals: int
    goals_per_match: float
    most_scored_match: MatchBrief | None
    last_match: MatchBrief | None


class PlayerStats(BaseModel):
    player_id: UUID
    name: str
    active: bool
    matches_played: int
    wins: int
    losses: int
    draws: int
    win_rate: float
    goals_for: int
    own_goals: int
    net_goals: int
    current_win_streak: int
    best_win_streak: int
    goals_per_match: float
    eligible_for_win_rate_ranking: bool


class Rankings(BaseModel):
    minimum_matches_for_win_rate: int
    top_scorers: list[PlayerStats]
    own_goal_kings: list[PlayerStats]
    most_participative: list[PlayerStats]
    active_streaks: list[PlayerStats]
    best_win_rate: list[PlayerStats]
