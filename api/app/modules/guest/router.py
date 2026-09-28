from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.modules.groups.models import Group
from app.modules.groups.schemas import GroupOut
from app.modules.matches import service as match_service
from app.modules.matches.schemas import MatchOut
from app.modules.players.models import Player
from app.modules.players.schemas import PlayerOut
from app.modules.stats import service as stats_service
from app.modules.stats.schemas import GroupSummary, PlayerStats, Rankings

router = APIRouter(prefix="/guest/{code}", tags=["guest"])


def _group_by_code(db: Session, code: str) -> Group:
    group = db.scalar(select(Group).where(Group.code == code.upper()))
    if not group:
        raise NotFoundError("Grupo no encontrado")
    return group


@router.get("", response_model=GroupOut)
def group_info(code: str, db: Annotated[Session, Depends(get_db)]):
    return _group_by_code(db, code)


@router.get("/players", response_model=list[PlayerOut])
def players(code: str, db: Annotated[Session, Depends(get_db)], include_inactive: bool = Query(False)):
    group = _group_by_code(db, code)
    stmt = select(Player).where(Player.group_id == group.id)
    if not include_inactive:
        stmt = stmt.where(Player.active.is_(True))
    return list(db.scalars(stmt.order_by(Player.name)))


@router.get("/players/{player_id}", response_model=PlayerOut)
def player_detail(code: str, player_id: UUID, db: Annotated[Session, Depends(get_db)]):
    group = _group_by_code(db, code)
    player = db.scalar(select(Player).where(Player.id == player_id, Player.group_id == group.id))
    if not player:
        raise NotFoundError("Jugador no encontrado")
    return player


@router.get("/players/{player_id}/stats", response_model=PlayerStats)
def player_stats(code: str, player_id: UUID, db: Annotated[Session, Depends(get_db)]):
    group = _group_by_code(db, code)
    result = stats_service.get_player_stats(db, group.id, player_id)
    if result is None:
        raise NotFoundError("Jugador no encontrado")
    return result


@router.get("/matches", response_model=list[MatchOut])
def matches(
    code: str,
    db: Annotated[Session, Depends(get_db)],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    player_id: UUID | None = Query(None),
):
    group = _group_by_code(db, code)
    return match_service.list_public_matches(
        db, group.id, offset=offset, limit=limit, player_id=player_id
    )


@router.get("/matches/{match_id}", response_model=MatchOut)
def match_detail(code: str, match_id: UUID, db: Annotated[Session, Depends(get_db)]):
    group = _group_by_code(db, code)
    return match_service.get_public_match(db, group.id, match_id)


@router.get("/stats/summary", response_model=GroupSummary)
def summary(code: str, db: Annotated[Session, Depends(get_db)]):
    group = _group_by_code(db, code)
    return stats_service.get_summary(db, group.id)


@router.get("/stats/players", response_model=list[PlayerStats])
def all_player_stats(code: str, db: Annotated[Session, Depends(get_db)]):
    group = _group_by_code(db, code)
    return stats_service.get_all_player_stats(db, group.id)


@router.get("/stats/rankings", response_model=Rankings)
def rankings(code: str, db: Annotated[Session, Depends(get_db)], limit: int = Query(10, ge=1, le=100)):
    group = _group_by_code(db, code)
    return stats_service.get_rankings(db, group.id, None, limit)
