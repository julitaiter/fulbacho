from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.stats import service
from app.modules.stats.schemas import GroupSummary, PlayerStats, Rankings

router = APIRouter(prefix="/groups/{group_id}/stats", tags=["stats"])


@router.get("/summary", response_model=GroupSummary)
def summary(group_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.get_summary(db, group_id, user)


@router.get("/players", response_model=list[PlayerStats])
def player_stats_list(group_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.get_all_player_stats(db, group_id, user)


@router.get("/rankings", response_model=Rankings)
def rankings(group_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)], limit: int = Query(10, ge=1, le=100)):
    return service.get_rankings(db, group_id, user, limit)


@router.get("/players/{player_id}", response_model=PlayerStats)
def player_stats(group_id: UUID, player_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    result = service.get_player_stats(db, group_id, player_id, user)
    if result is None:
        raise NotFoundError("Jugador no encontrado")
    return result
