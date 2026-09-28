from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import PermissionError
from app.modules.auth.models import User
from app.modules.groups.models import GroupMember, GroupRole


def get_membership(db: Session, group_id: UUID, user_id: UUID) -> GroupMember | None:
    return db.scalar(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    )


def require_member(db: Session, group_id: UUID, user: User) -> GroupMember:
    membership = get_membership(db, group_id, user.id)
    if not membership:
        raise PermissionError("No pertenecés a este grupo")
    return membership


def require_admin(db: Session, group_id: UUID, user: User) -> GroupMember:
    membership = require_member(db, group_id, user)
    if membership.role != GroupRole.ADMIN:
        raise PermissionError("Se requiere rol admin")
    return membership
