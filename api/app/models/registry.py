"""Central SQLAlchemy model registry.

Import this module from Alembic (or other metadata discovery tooling) so all
mapped models are registered in ``Base.metadata``. Application model modules
must import only from ``app.models.base`` to avoid circular imports.
"""

from app.models.base import Base
from app.modules.auth.models import RefreshToken, User
from app.modules.groups.models import Group, GroupMember
from app.modules.matches.models import Goal, Match, MatchParticipant
from app.modules.players.models import Player

__all__ = [
    "Base",
    "User",
    "RefreshToken",
    "Group",
    "GroupMember",
    "Player",
    "Match",
    "MatchParticipant",
    "Goal",
]
