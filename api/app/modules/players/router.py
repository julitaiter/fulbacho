from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.players import service
from app.modules.players.schemas import (
    AttachCasualRequest,
    CasualParticipantOut,
    PlayerCreate,
    PlayerOut,
    PlayerUpdate,
    PromoteCasualRequest,
)

router = APIRouter(prefix="/groups/{group_id}/players", tags=["players"])


@router.get("", response_model=list[PlayerOut])
def list_players(group_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)], include_inactive: bool = Query(False)):
    return service.list_players(db, group_id, user, include_inactive)


@router.post("", response_model=PlayerOut, status_code=status.HTTP_201_CREATED)
def create_player(group_id: UUID, payload: PlayerCreate, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.create_player(db, group_id, user, payload.name, payload.linked_user_id)


@router.get("/casuals", response_model=list[CasualParticipantOut])
def list_casuals(group_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.list_casual_participants(db, group_id, user)


@router.post("/promote-casual", response_model=PlayerOut, status_code=status.HTTP_201_CREATED)
def promote_casual(group_id: UUID, payload: PromoteCasualRequest, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.promote_casual(db, group_id, user, **payload.model_dump())


@router.get("/{player_id}", response_model=PlayerOut)
def get_player(group_id: UUID, player_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.get_player(db, group_id, player_id, user)


@router.patch("/{player_id}", response_model=PlayerOut)
def update_player(group_id: UUID, player_id: UUID, payload: PlayerUpdate, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    fields = payload.model_fields_set
    return service.update_player(
        db,
        group_id,
        player_id,
        user,
        name=payload.name,
        linked_user_id=payload.linked_user_id,
        linked_user_provided="linked_user_id" in fields,
        active=payload.active,
        active_provided="active" in fields,
    )


@router.delete("/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_player(group_id: UUID, player_id: UUID, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    service.deactivate_player(db, group_id, player_id, user)


@router.post("/{player_id}/attach-casual", response_model=PlayerOut)
def attach_casual(group_id: UUID, player_id: UUID, payload: AttachCasualRequest, user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    return service.attach_casual(db, group_id, player_id, user, payload.participant_ids)
