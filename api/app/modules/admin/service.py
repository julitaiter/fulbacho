from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.modules.auth.models import User
from app.modules.groups.models import Group, GroupMember
from app.modules.matches.models import Match
from app.modules.matches.service import _serialize_match


def get_resource(db: Session, model, resource_id: UUID):
    resource = db.get(model, resource_id)
    if resource is None:
        raise NotFoundError("Recurso no encontrado")
    return resource


def list_users(db: Session, offset: int, limit: int):
    return list(db.scalars(select(User).order_by(User.email, User.id).offset(offset).limit(limit)))


def update_user(db: Session, user_id: UUID, payload):
    user = get_resource(db, User, user_id)
    for key, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


def list_groups(db: Session, offset: int, limit: int):
    return list(db.scalars(select(Group).order_by(Group.created_at.desc(), Group.id).offset(offset).limit(limit)))


def list_members(db: Session, group_id: UUID):
    get_resource(db, Group, group_id)
    rows = db.execute(
        select(GroupMember, User).join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
        .order_by(GroupMember.joined_at, GroupMember.id)
    ).all()
    return [
        {
            "id": member.id, "user_id": user.id, "email": user.email,
            "display_name": user.display_name, "role": member.role,
            "joined_at": member.joined_at,
        }
        for member, user in rows
    ]


def list_matches(db: Session, offset: int, limit: int):
    matches = db.scalars(
        select(Match).order_by(Match.played_at.desc(), Match.id).offset(offset).limit(limit)
    )
    return [_serialize_match(db, match) for match in matches]


def get_match(db: Session, match_id: UUID):
    return _serialize_match(db, get_resource(db, Match, match_id))
