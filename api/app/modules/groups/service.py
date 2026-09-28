import secrets
import string
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.auth.models import User
from app.modules.groups.models import Group, GroupMember, GroupRole
from app.modules.groups.permissions import require_admin, require_member

ALPHABET = string.ascii_uppercase + string.digits


def _new_code(db: Session) -> str:
    for _ in range(30):
        code = "".join(secrets.choice(ALPHABET) for _ in range(6))
        if not db.scalar(select(Group.id).where(Group.code == code)):
            return code
    raise ConflictError("No se pudo generar un código de grupo")


def create_group(db: Session, user: User, name: str) -> Group:
    group = Group(name=name.strip(), code=_new_code(db), created_by_id=user.id)
    db.add(group)
    db.flush()
    db.add(GroupMember(group_id=group.id, user_id=user.id, role=GroupRole.ADMIN))
    db.commit()
    db.refresh(group)
    return group


def list_groups(db: Session, user: User) -> list[Group]:
    return list(
        db.scalars(
            select(Group)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(GroupMember.user_id == user.id)
            .order_by(Group.name)
        )
    )



def list_group_overview(db: Session, user: User):
    memberships = db.execute(
        select(Group, GroupMember)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == user.id)
        .order_by(Group.name)
    ).all()
    from app.modules.matches.models import Match
    from app.modules.players.models import Player

    result = []
    for group, membership in memberships:
        players_count = db.scalar(
            select(func.count()).select_from(Player).where(
                Player.group_id == group.id, Player.active.is_(True)
            )
        ) or 0
        matches_count = db.scalar(
            select(func.count()).select_from(Match).where(Match.group_id == group.id)
        ) or 0
        result.append({
            "id": group.id,
            "name": group.name,
            "code": group.code,
            "created_by_id": group.created_by_id,
            "created_at": group.created_at,
            "players_count": players_count,
            "matches_count": matches_count,
            "role": membership.role,
        })
    return result

def get_group(db: Session, group_id: UUID, user: User) -> Group:
    require_member(db, group_id, user)
    group = db.get(Group, group_id)
    if not group:
        raise NotFoundError("Grupo no encontrado")
    return group


def update_group(db: Session, group_id: UUID, user: User, name: str) -> Group:
    require_admin(db, group_id, user)
    group = db.get(Group, group_id)
    if not group:
        raise NotFoundError("Grupo no encontrado")
    group.name = name.strip()
    db.commit()
    db.refresh(group)
    return group


def join_group(db: Session, user: User, code: str) -> Group:
    group = db.scalar(select(Group).where(Group.code == code.strip().upper()))
    if not group:
        raise NotFoundError("Código de grupo inexistente")
    existing = db.scalar(
        select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == user.id)
    )
    if not existing:
        db.add(GroupMember(group_id=group.id, user_id=user.id, role=GroupRole.MEMBER))
        db.commit()
    return group


def list_members(db: Session, group_id: UUID, user: User):
    require_member(db, group_id, user)
    rows = db.execute(
        select(GroupMember, User)
        .join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
        .order_by(GroupMember.joined_at)
    ).all()
    return [
        {
            "id": membership.id,
            "user_id": target.id,
            "email": target.email,
            "display_name": target.display_name,
            "role": membership.role,
            "joined_at": membership.joined_at,
        }
        for membership, target in rows
    ]


def _admin_count(db: Session, group_id: UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.role == GroupRole.ADMIN
        )
    ) or 0


def update_member_role(db: Session, group_id: UUID, target_user_id: UUID, role: GroupRole, user: User):
    require_admin(db, group_id, user)
    membership = db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == target_user_id
        )
    )
    if not membership:
        raise NotFoundError("Miembro no encontrado")
    if membership.role == GroupRole.ADMIN and role != GroupRole.ADMIN and _admin_count(db, group_id) <= 1:
        raise ConflictError("El grupo debe conservar al menos un admin")
    membership.role = role
    db.commit()
    return membership


def remove_member(db: Session, group_id: UUID, target_user_id: UUID, user: User) -> None:
    require_admin(db, group_id, user)
    membership = db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == target_user_id
        )
    )
    if not membership:
        raise NotFoundError("Miembro no encontrado")
    if membership.role == GroupRole.ADMIN and _admin_count(db, group_id) <= 1:
        raise ConflictError("No se puede eliminar al único admin")
    from app.modules.players.models import Player

    linked_players = list(
        db.scalars(
            select(Player).where(
                Player.group_id == group_id,
                Player.linked_user_id == target_user_id,
            )
        )
    )
    for player in linked_players:
        player.linked_user_id = None
    db.delete(membership)
    db.commit()
