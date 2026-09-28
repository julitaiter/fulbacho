from collections import Counter
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.auth.models import User
from app.modules.groups.permissions import require_member
from app.modules.matches.models import Goal, Match, MatchParticipant, TeamSide
from app.modules.matches.schemas import MatchCreate
from app.modules.players.models import Player


def _match_score(db: Session, match_id: UUID) -> tuple[int, int]:
    rows = db.execute(
        select(Goal.team_scored_for, func.count(Goal.id))
        .where(Goal.match_id == match_id)
        .group_by(Goal.team_scored_for)
    ).all()
    counts = {team: count for team, count in rows}
    return counts.get(TeamSide.A, 0), counts.get(TeamSide.B, 0)


def _can_edit(match: Match) -> bool:
    now = datetime.now(UTC)
    created = match.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    return now <= created + timedelta(hours=24)


def _serialize_match(db: Session, match: Match):
    participants = list(db.scalars(select(MatchParticipant).where(MatchParticipant.match_id == match.id)))
    goals = list(db.scalars(select(Goal).where(Goal.match_id == match.id).order_by(Goal.created_at, Goal.id)))
    score_a, score_b = _match_score(db, match.id)
    return {
        "id": match.id,
        "group_id": match.group_id,
        "played_at": match.played_at,
        "players_per_team": match.players_per_team,
        "location": match.location,
        "team_a_name": match.team_a_name,
        "team_b_name": match.team_b_name,
        "score_a": score_a,
        "score_b": score_b,
        "created_by_id": match.created_by_id,
        "created_at": match.created_at,
        "updated_at": match.updated_at,
        "can_edit": _can_edit(match),
        "participants": participants,
        "goals": goals,
    }


def list_matches(
    db: Session,
    group_id: UUID,
    user: User,
    *,
    offset: int = 0,
    limit: int = 50,
    player_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    require_member(db, group_id, user)
    stmt = select(Match).where(Match.group_id == group_id)
    if player_id is not None:
        stmt = stmt.join(MatchParticipant, MatchParticipant.match_id == Match.id).where(
            MatchParticipant.player_id == player_id
        )
    if date_from is not None:
        stmt = stmt.where(func.date(Match.played_at) >= date_from)
    if date_to is not None:
        stmt = stmt.where(func.date(Match.played_at) <= date_to)
    matches = list(
        db.scalars(
            stmt.distinct().order_by(Match.played_at.desc()).offset(offset).limit(limit)
        )
    )
    return [_serialize_match(db, match) for match in matches]


def get_match(db: Session, group_id: UUID, match_id: UUID, user: User):
    require_member(db, group_id, user)
    match = db.scalar(select(Match).where(Match.id == match_id, Match.group_id == group_id))
    if not match:
        raise NotFoundError("Partido no encontrado")
    return _serialize_match(db, match)


def _validate_and_prepare(db: Session, group_id: UUID, payload: MatchCreate):
    if len(payload.team_a.participants) < payload.players_per_team:
        raise ConflictError(f"Equipo A requiere al menos {payload.players_per_team} participantes")
    if len(payload.team_b.participants) < payload.players_per_team:
        raise ConflictError(f"Equipo B requiere al menos {payload.players_per_team} participantes")

    all_inputs = [(TeamSide.A, p) for p in payload.team_a.participants] + [
        (TeamSide.B, p) for p in payload.team_b.participants
    ]
    refs = [participant.ref for _, participant in all_inputs]
    if len(refs) != len(set(refs)):
        raise ConflictError("Los ref de participantes deben ser únicos")

    player_ids = [participant.player_id for _, participant in all_inputs if participant.player_id]
    if len(player_ids) != len(set(player_ids)):
        raise ConflictError("Un jugador habitual no puede aparecer dos veces en el partido")

    players = {}
    if player_ids:
        rows = list(
            db.scalars(
                select(Player).where(
                    Player.id.in_(player_ids),
                    Player.group_id == group_id,
                    Player.active.is_(True),
                )
            )
        )
        players = {player.id: player for player in rows}
        if len(players) != len(player_ids):
            raise ConflictError("Todos los jugadores habituales deben existir, estar activos y pertenecer al grupo")

    participant_defs = []
    team_by_ref = {}
    for team, item in all_inputs:
        team_by_ref[item.ref] = team
        name = players[item.player_id].name if item.player_id else item.name.strip()
        participant_defs.append((team, item, name))

    explicit_goals = Counter({TeamSide.A: 0, TeamSide.B: 0})
    normalized_goals = []
    for goal in payload.goals:
        if goal.participant_ref is None:
            team_scored_for = goal.team_scored_for
        else:
            if goal.participant_ref not in team_by_ref:
                raise ConflictError(f"participant_ref inexistente: {goal.participant_ref}")
            participant_team = team_by_ref[goal.participant_ref]
            expected_team = TeamSide.other(participant_team) if goal.own_goal else participant_team
            if goal.team_scored_for is not None and goal.team_scored_for != expected_team:
                raise ConflictError("team_scored_for no coincide con el tipo de gol")
            team_scored_for = expected_team
        explicit_goals[team_scored_for] += 1
        normalized_goals.append((goal, team_scored_for))

    if explicit_goals[TeamSide.A] > payload.team_a.score:
        raise ConflictError("Los goles detallados de A superan el marcador")
    if explicit_goals[TeamSide.B] > payload.team_b.score:
        raise ConflictError("Los goles detallados de B superan el marcador")

    anonymous_a = payload.team_a.score - explicit_goals[TeamSide.A]
    anonymous_b = payload.team_b.score - explicit_goals[TeamSide.B]
    return participant_defs, normalized_goals, anonymous_a, anonymous_b


def _persist_contents(db: Session, match: Match, payload: MatchCreate):
    participant_defs, normalized_goals, anonymous_a, anonymous_b = _validate_and_prepare(
        db, match.group_id, payload
    )
    now = datetime.now(UTC)
    ref_to_participant = {}
    for team, item, display_name in participant_defs:
        participant = MatchParticipant(
            match_id=match.id,
            player_id=item.player_id,
            display_name=display_name,
            team=team,
            created_at=now,
        )
        db.add(participant)
        db.flush()
        ref_to_participant[item.ref] = participant

    for goal_input, team_scored_for in normalized_goals:
        participant_id = (
            ref_to_participant[goal_input.participant_ref].id
            if goal_input.participant_ref is not None
            else None
        )
        db.add(
            Goal(
                match_id=match.id,
                participant_id=participant_id,
                own_goal=goal_input.own_goal,
                team_scored_for=team_scored_for,
                created_at=now,
            )
        )
    for _ in range(anonymous_a):
        db.add(Goal(match_id=match.id, participant_id=None, own_goal=False, team_scored_for=TeamSide.A, created_at=now))
    for _ in range(anonymous_b):
        db.add(Goal(match_id=match.id, participant_id=None, own_goal=False, team_scored_for=TeamSide.B, created_at=now))


def create_match(db: Session, group_id: UUID, user: User, payload: MatchCreate):
    require_member(db, group_id, user)
    try:
        match = Match(
            group_id=group_id,
            played_at=payload.played_at,
            players_per_team=payload.players_per_team,
            location=payload.location,
            team_a_name=payload.team_a.name.strip(),
            team_b_name=payload.team_b.name.strip(),
            created_by_id=user.id,
        )
        db.add(match)
        db.flush()
        _persist_contents(db, match, payload)
        db.commit()
        db.refresh(match)
    except Exception:
        db.rollback()
        raise
    return _serialize_match(db, match)


def update_match(db: Session, group_id: UUID, match_id: UUID, user: User, payload: MatchCreate):
    require_member(db, group_id, user)
    match = db.scalar(select(Match).where(Match.id == match_id, Match.group_id == group_id))
    if not match:
        raise NotFoundError("Partido no encontrado")
    if not _can_edit(match):
        raise ConflictError("El partido ya superó la ventana de edición de 24 horas")
    try:
        _validate_and_prepare(db, group_id, payload)
        db.execute(delete(Goal).where(Goal.match_id == match.id))
        db.execute(delete(MatchParticipant).where(MatchParticipant.match_id == match.id))
        match.played_at = payload.played_at
        match.players_per_team = payload.players_per_team
        match.location = payload.location
        match.team_a_name = payload.team_a.name.strip()
        match.team_b_name = payload.team_b.name.strip()
        db.flush()
        _persist_contents(db, match, payload)
        db.commit()
        db.refresh(match)
    except Exception:
        db.rollback()
        raise
    return _serialize_match(db, match)


def get_public_match(db: Session, group_id: UUID, match_id: UUID):
    match = db.scalar(select(Match).where(Match.id == match_id, Match.group_id == group_id))
    if not match:
        raise NotFoundError("Partido no encontrado")
    return _serialize_match(db, match)


def list_public_matches(
    db: Session,
    group_id: UUID,
    *,
    offset: int = 0,
    limit: int = 50,
    player_id: UUID | None = None,
):
    stmt = select(Match).where(Match.group_id == group_id)
    if player_id is not None:
        stmt = stmt.join(MatchParticipant, MatchParticipant.match_id == Match.id).where(
            MatchParticipant.player_id == player_id
        )
    matches = list(
        db.scalars(
            stmt.distinct()
            .order_by(Match.played_at.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return [_serialize_match(db, match) for match in matches]
