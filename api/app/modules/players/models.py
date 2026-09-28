import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Player(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "players"

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    linked_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


Index(
    "uq_player_group_linked_user_not_null",
    Player.group_id,
    Player.linked_user_id,
    unique=True,
    postgresql_where=Player.linked_user_id.is_not(None),
)
