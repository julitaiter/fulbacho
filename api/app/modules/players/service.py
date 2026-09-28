from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, PermissionError
from app.modules.auth.models import User
from app.modules.groups.models import GroupMember, GroupRole
from app.modules.groups.permissions import require_member
from app.modules.matches.models import Match, MatchParticipant
from app.modules.players.models import Player


def _validate_linked_user(db: Session, group_id: UUID, linked_user_id: UUID | None, requester: User):
    if linked_user_id is None:
        return
    membership = db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == linked_user_id
        )
    )
    if not membership:
        raise ConflictError("El usuario vinculado debe ser miembro del grupo")
    requester_membership = require_member(db, group_id, requester)
    if linked_user_id != requester.id and requester_membership.role != GroupRole.ADMIN:
        raise PermissionError("Solo un admin puede vincular a otro usuario")
    existing = db.scalar(
        select(Player).where(
            Player.group_id == group_id,
            Player.linked_user_id == linked_user_id,
        )
    )
    if existing:
        raise ConflictError("Ese usuario ya está vinculado a otro jugador del grupo")


def list_players(db: Session, group_id: UUID, user: User, include_inactive: bool = False):
    require_member(db, group_id, user)
    stmt = select(Player).where(Player.group_id == group_id)
    if not include_inactive:
        stmt = stmt.where(Player.active.is_(True))
    return list(db.scalars(stmt.order_by(Player.name)))


def create_player(db: Session, group_id: UUID, user: User, name: str, linked_user_id: UUID | None):
    require_member(db, group_id, user)
    _validate_linked_user(db, group_id, linked_user_id, user)
    player = Player(group_id=group_id, name=name.strip(), linked_user_id=linked_user_id, active=True)
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def get_player(db: Session, group_id: UUID, player_id: UUID, user: User):
    require_member(db, group_id, user)
    player = db.scalar(select(Player).where(Player.id == player_id, Player.group_id == group_id))
    if not player:
        raise NotFoundError("Jugador no encontrado")
    return player


def update_player(db: Session, group_id: UUID, player_id: UUID, user: User, *, name=None, linked_user_id=None, linked_user_provided=False, active=None, active_provided=False):
    player = get_player(db, group_id, player_id, user)
    if name is not None:
        player.name = name.strip()
    if linked_user_provided:
        if linked_user_id != player.linked_user_id:
            _validate_linked_user(db, group_id, linked_user_id, user)
        player.linked_user_id = linked_user_id
    if active_provided:
        player.active = bool(active)
    db.commit()
    db.refresh(player)
    return player


def deactivate_player(db: Session, group_id: UUID, player_id: UUID, user: User):
    player = get_player(db, group_id, player_id, user)
    player.active = False
    db.commit()


def _get_casual_participants(db: Session, group_id: UUID, participant_ids: list[UUID]):
    if len(set(participant_ids)) != len(participant_ids):
        raise ConflictError("Hay participant_ids duplicados")
    participants = list(
        db.scalars(
            select(MatchParticipant)
            .join(Match, Match.id == MatchParticipant.match_id)
            .where(
                Match.group_id == group_id,
                MatchParticipant.id.in_(participant_ids),
            )
        )
    )
    if len(participants) != len(participant_ids):
        raise NotFoundError("Una o más participaciones no pertenecen al grupo")
    if any(p.player_id is not None for p in participants):
        raise ConflictError("Solo se pueden asociar participaciones casuales")
    return participants


def list_casual_participants(db: Session, group_id: UUID, user: User):
    require_member(db, group_id, user)
    rows = db.execute(
        select(MatchParticipant, Match)
        .join(Match, Match.id == MatchParticipant.match_id)
        .where(Match.group_id == group_id, MatchParticipant.player_id.is_(None))
        .order_by(Match.played_at.desc(), MatchParticipant.display_name)
    ).all()
    return [
        {
            "id": participant.id,
            "match_id": match.id,
            "match_played_at": match.played_at,
            "display_name": participant.display_name,
            "team": participant.team.value,
        }
        for participant, match in rows
    ]


def promote_casual(db: Session, group_id: UUID, user: User, *, name: str, participant_ids: list[UUID], linked_user_id: UUID | None):
    require_member(db, group_id, user)
    _validate_linked_user(db, group_id, linked_user_id, user)
    participants = _get_casual_participants(db, group_id, participant_ids)
    player = Player(group_id=group_id, name=name.strip(), linked_user_id=linked_user_id, active=True)
    db.add(player)
    db.flush()
    for participant in participants:
        participant.player_id = player.id
    db.commit()
    db.refresh(player)
    return player


def attach_casual(db: Session, group_id: UUID, player_id: UUID, user: User, participant_ids: list[UUID]):
    player = get_player(db, group_id, player_id, user)
    participants = _get_casual_participants(db, group_id, participant_ids)
    match_ids = [p.match_id for p in participants]
    existing_match_ids = set(
        db.scalars(
            select(MatchParticipant.match_id).where(
                MatchParticipant.player_id == player.id,
                MatchParticipant.match_id.in_(match_ids),
            )
        )
    )
    if existing_match_ids:
        raise ConflictError("El jugador ya participa en uno de los partidos seleccionados")
    for participant in participants:
        participant.player_id = player.id
    db.commit()
    db.refresh(player)
    return player
