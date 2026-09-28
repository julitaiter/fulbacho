from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.matches import service
from app.modules.matches.schemas import MatchCreate, MatchOut, MatchUpdate

router = APIRouter(prefix="/groups/{group_id}/matches", tags=["matches"])


@router.get("", response_model=list[MatchOut])
def list_matches(
    group_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    player_id: UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    return service.list_matches(
        db,
        group_id,
        user,
        offset=offset,
        limit=limit,
        player_id=player_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("", response_model=MatchOut, status_code=status.HTTP_201_CREATED)
def create_match(group_id: UUID, payload: MatchCreate, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.create_match(db, group_id, user, payload)


@router.get("/{match_id}", response_model=MatchOut)
def get_match(group_id: UUID, match_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.get_match(db, group_id, match_id, user)


@router.put("/{match_id}", response_model=MatchOut)
def update_match(group_id: UUID, match_id: UUID, payload: MatchUpdate, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.update_match(db, group_id, match_id, user, payload)
