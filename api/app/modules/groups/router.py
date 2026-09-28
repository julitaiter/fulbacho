from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.groups import service
from app.modules.groups.schemas import (
    GroupCreate,
    GroupJoin,
    GroupOut,
    GroupOverview,
    GroupUpdate,
    MemberOut,
    MemberRoleUpdate,
)

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", response_model=list[GroupOut])
def list_groups(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.list_groups(db, user)


@router.get("/overview", response_model=list[GroupOverview])
def list_group_overview(user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.list_group_overview(db, user)


@router.post("", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(payload: GroupCreate, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.create_group(db, user, payload.name)


@router.post("/join", response_model=GroupOut)
def join_group(payload: GroupJoin, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.join_group(db, user, payload.code)


@router.get("/{group_id}", response_model=GroupOut)
def get_group(group_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.get_group(db, group_id, user)


@router.patch("/{group_id}", response_model=GroupOut)
def update_group(group_id: UUID, payload: GroupUpdate, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.update_group(db, group_id, user, payload.name)


@router.get("/{group_id}/members", response_model=list[MemberOut])
def list_members(group_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.list_members(db, group_id, user)


@router.patch("/{group_id}/members/{target_user_id}", response_model=MemberOut)
def update_member_role(group_id: UUID, target_user_id: UUID, payload: MemberRoleUpdate, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    service.update_member_role(db, group_id, target_user_id, payload.role, user)
    return next(item for item in service.list_members(db, group_id, user) if item["user_id"] == target_user_id)


@router.delete("/{group_id}/members/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(group_id: UUID, target_user_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    service.remove_member(db, group_id, target_user_id, user)
