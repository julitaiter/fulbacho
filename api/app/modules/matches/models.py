import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class TeamSide(str, enum.Enum):
    A = "A"
    B = "B"

    @classmethod
    def other(cls, team: "TeamSide") -> "TeamSide":
        return cls.B if team == cls.A else cls.A


TEAM_SIDE_ENUM = Enum(
    TeamSide,
    name="team_side",
    values_callable=lambda enum_cls: [item.value for item in enum_cls],
)


class Match(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "matches"
    __table_args__ = (
        CheckConstraint("players_per_team > 0", name="ck_match_players_per_team_positive"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    played_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    players_per_team: Mapped[int] = mapped_column(nullable=False)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    team_a_name: Mapped[str] = mapped_column(String(100), default="Equipo A", nullable=False)
    team_b_name: Mapped[str] = mapped_column(String(100), default="Equipo B", nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class MatchParticipant(UUIDMixin, Base):
    __tablename__ = "match_participants"
    __table_args__ = (UniqueConstraint("match_id", "player_id", name="uq_match_player"),)

    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), index=True
    )
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("players.id", ondelete="SET NULL"), nullable=True, index=True
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    team: Mapped[TeamSide] = mapped_column(TEAM_SIDE_ENUM, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Goal(UUIDMixin, Base):
    __tablename__ = "goals"

    match_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), index=True
    )
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("match_participants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    own_goal: Mapped[bool] = mapped_column(default=False, nullable=False)
    team_scored_for: Mapped[TeamSide] = mapped_column(TEAM_SIDE_ENUM, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
