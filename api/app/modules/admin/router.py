from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin import service
from app.modules.admin.schemas import UserAdminUpdate
from app.modules.auth.dependencies import require_superuser
from app.modules.auth.models import User
from app.modules.auth.schemas import UserOut
from app.modules.groups.models import Group
from app.modules.groups.schemas import GroupOut, MemberOut
from app.modules.matches.schemas import MatchOut

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_superuser)])
Database = Annotated[Session, Depends(get_db)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.get("/users", response_model=list[UserOut])
def list_users(db: Database, offset: Offset = 0, limit: Limit = 50):
    return service.list_users(db, offset, limit)


@router.get("/users/{user_id}", response_model=UserOut)
def user_detail(user_id: UUID, db: Database):
    return service.get_resource(db, User, user_id)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: UUID, payload: UserAdminUpdate, db: Database):
    return service.update_user(db, user_id, payload)


@router.get("/groups", response_model=list[GroupOut])
def list_groups(db: Database, offset: Offset = 0, limit: Limit = 50):
    return service.list_groups(db, offset, limit)


@router.get("/groups/{group_id}", response_model=GroupOut)
def group_detail(group_id: UUID, db: Database):
    return service.get_resource(db, Group, group_id)


@router.get("/groups/{group_id}/members", response_model=list[MemberOut])
def group_members(group_id: UUID, db: Database):
    return service.list_members(db, group_id)


@router.get("/matches", response_model=list[MatchOut])
def list_matches(db: Database, offset: Offset = 0, limit: Limit = 50):
    return service.list_matches(db, offset, limit)


@router.get("/matches/{match_id}", response_model=MatchOut)
def match_detail(match_id: UUID, db: Database):
    return service.get_match(db, match_id)
