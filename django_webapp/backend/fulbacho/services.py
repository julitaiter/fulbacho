from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .access import ensure_group_member
from .models import (
    FriendGroup,
    Goal,
    GroupMember,
    GroupRole,
    Match,
    MatchPlayer,
    Player,
    Team,
)


@dataclass(frozen=True)
class MatchPayload:
    group: FriendGroup
    played_at: object
    modality: str
    location: str
    team_a_name: str
    team_b_name: str
    score_a: int
    score_b: int
    team_a_player_ids: list
    team_b_player_ids: list
    goals: list[dict]


def create_group(*, user, name: str) -> FriendGroup:
    with transaction.atomic():
        group = FriendGroup.objects.create(name=name, created_by=user)
        GroupMember.objects.create(group=group, user=user, role=GroupRole.ADMIN)
    return group


def join_group_by_code(*, user, code: str) -> FriendGroup:
    code = (code or "").strip().upper()
    if len(code) != 6:
        raise ValidationError("El código debe tener 6 caracteres.")

    try:
        group = FriendGroup.objects.get(code=code)
    except FriendGroup.DoesNotExist as exc:
        raise ValidationError("No existe un grupo con ese código.") from exc

    GroupMember.objects.get_or_create(
        group=group,
        user=user,
        defaults={"role": GroupRole.MEMBER},
    )
    return group


def _unique_list(values: Iterable) -> list:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _validate_rosters(
    *,
    group: FriendGroup,
    team_a_player_ids: list,
    team_b_player_ids: list,
) -> tuple[dict, dict]:
    team_a_player_ids = _unique_list(team_a_player_ids)
    team_b_player_ids = _unique_list(team_b_player_ids)

    if len(team_a_player_ids) < 2 or len(team_b_player_ids) < 2:
        raise ValidationError("El partido necesita al menos 2 jugadores por equipo.")

    overlap = set(team_a_player_ids).intersection(set(team_b_player_ids))
    if overlap:
        raise ValidationError("Un jugador no puede estar en los dos equipos.")

    all_ids = set(team_a_player_ids).union(set(team_b_player_ids))
    players = Player.objects.filter(group=group, id__in=all_ids, active=True)
    player_map = {player.id: player for player in players}

    missing = all_ids.difference(set(player_map.keys()))
    if missing:
        raise ValidationError("Todos los jugadores deben existir, estar activos y pertenecer al grupo.")

    team_map = {player_id: Team.A for player_id in team_a_player_ids}
    team_map.update({player_id: Team.B for player_id in team_b_player_ids})
    return player_map, team_map


def _validate_goals(
    *,
    group: FriendGroup,
    team_map: dict,
    goals: list[dict],
    score_a: int,
    score_b: int,
) -> None:
    if score_a < 0 or score_b < 0:
        raise ValidationError("Los marcadores no pueden ser negativos.")

    goal_counts = {Team.A: 0, Team.B: 0}
    for goal in goals:
        team_scored_for = goal.get("team_scored_for")
        own_goal = bool(goal.get("own_goal", False))
        player = goal.get("player")

        if team_scored_for not in {Team.A, Team.B, "A", "B"}:
            raise ValidationError("Equipo inválido en una fila de gol.")

        goal_counts[team_scored_for] += 1

        if player is not None:
            if player.group_id != group.id:
                raise ValidationError("El jugador del gol debe pertenecer al grupo.")
            if player.id not in team_map:
                raise ValidationError("El jugador del gol debe ser parte del partido.")

            player_team = team_map[player.id]
            if own_goal and player_team == team_scored_for:
                raise ValidationError("Un gol en contra debe sumarse al equipo contrario.")
            if not own_goal and player_team != team_scored_for:
                raise ValidationError("Un gol normal debe sumarse al equipo del jugador.")
        elif own_goal:
            raise ValidationError("Los goles en contra necesitan jugador para aplicar la penalización.")

    if goal_counts[Team.A] > score_a or goal_counts[Team.B] > score_b:
        raise ValidationError("Los goles cargados no pueden superar el marcador final.")


def _build_payload(validated_data: dict) -> MatchPayload:
    return MatchPayload(
        group=validated_data["group"],
        played_at=validated_data.get("played_at") or timezone.now(),
        modality=validated_data["modality"],
        location=validated_data.get("location", ""),
        team_a_name=validated_data.get("team_a_name") or "Equipo A",
        team_b_name=validated_data.get("team_b_name") or "Equipo B",
        score_a=validated_data.get("score_a", 0),
        score_b=validated_data.get("score_b", 0),
        team_a_player_ids=list(validated_data.pop("team_a_players")),
        team_b_player_ids=list(validated_data.pop("team_b_players")),
        goals=list(validated_data.pop("goals", [])),
    )


@transaction.atomic
def create_match(*, created_by, validated_data: dict) -> Match:
    payload = _build_payload(validated_data)
    ensure_group_member(created_by, payload.group)

    player_map, team_map = _validate_rosters(
        group=payload.group,
        team_a_player_ids=payload.team_a_player_ids,
        team_b_player_ids=payload.team_b_player_ids,
    )
    _validate_goals(
        group=payload.group,
        team_map=team_map,
        goals=payload.goals,
        score_a=payload.score_a,
        score_b=payload.score_b,
    )

    match = Match.objects.create(
        group=payload.group,
        played_at=payload.played_at,
        modality=payload.modality,
        location=payload.location,
        team_a_name=payload.team_a_name,
        team_b_name=payload.team_b_name,
        score_a=payload.score_a,
        score_b=payload.score_b,
        created_by=created_by,
    )

    MatchPlayer.objects.bulk_create(
        [
            MatchPlayer(match=match, player=player_map[player_id], team=team_map[player_id])
            for player_id in team_map
        ]
    )
    Goal.objects.bulk_create(
        [
            Goal(
                match=match,
                player=goal.get("player"),
                own_goal=bool(goal.get("own_goal", False)),
                team_scored_for=goal["team_scored_for"],
            )
            for goal in payload.goals
        ]
    )
    return match


@transaction.atomic
def replace_match(*, match: Match, user, validated_data: dict) -> Match:
    if not match.can_be_edited:
        raise ValidationError("Los partidos solo pueden editarse durante las primeras 24 horas.")

    payload = _build_payload(validated_data)
    if payload.group.id != match.group_id:
        raise ValidationError("No se puede mover un partido a otro grupo.")
    ensure_group_member(user, payload.group)

    player_map, team_map = _validate_rosters(
        group=payload.group,
        team_a_player_ids=payload.team_a_player_ids,
        team_b_player_ids=payload.team_b_player_ids,
    )
    _validate_goals(
        group=payload.group,
        team_map=team_map,
        goals=payload.goals,
        score_a=payload.score_a,
        score_b=payload.score_b,
    )

    match.played_at = payload.played_at
    match.modality = payload.modality
    match.location = payload.location
    match.team_a_name = payload.team_a_name
    match.team_b_name = payload.team_b_name
    match.score_a = payload.score_a
    match.score_b = payload.score_b
    match.save()

    match.match_players.all().delete()
    match.goals.all().delete()

    MatchPlayer.objects.bulk_create(
        [
            MatchPlayer(match=match, player=player_map[player_id], team=team_map[player_id])
            for player_id in team_map
        ]
    )
    Goal.objects.bulk_create(
        [
            Goal(
                match=match,
                player=goal.get("player"),
                own_goal=bool(goal.get("own_goal", False)),
                team_scored_for=goal["team_scored_for"],
            )
            for goal in payload.goals
        ]
    )
    return match


def _match_summary(match: Match | None) -> dict | None:
    if not match:
        return None
    return {
        "id": str(match.id),
        "played_at": match.played_at,
        "team_a_name": match.team_a_name,
        "team_b_name": match.team_b_name,
        "score_a": match.score_a,
        "score_b": match.score_b,
        "total_goals": match.score_a + match.score_b,
    }


def _result_for_match_player(match_player: MatchPlayer) -> str:
    match = match_player.match
    if match.score_a == match.score_b:
        return "draw"
    team_a_won = match.score_a > match.score_b
    if (match_player.team == Team.A and team_a_won) or (
        match_player.team == Team.B and not team_a_won
    ):
        return "win"
    return "loss"


def build_player_stats(player: Player) -> dict:
    appearances = list(
        player.match_players.select_related("match").order_by("match__played_at", "match__created_at")
    )
    played = len(appearances)
    wins = losses = draws = 0
    current_streak = 0
    best_streak = 0
    running_streak = 0

    for appearance in appearances:
        result = _result_for_match_player(appearance)
        if result == "win":
            wins += 1
            running_streak += 1
            best_streak = max(best_streak, running_streak)
        else:
            running_streak = 0
            if result == "draw":
                draws += 1
            else:
                losses += 1

    for appearance in reversed(appearances):
        if _result_for_match_player(appearance) == "win":
            current_streak += 1
        else:
            break

    goals_for = Goal.objects.filter(player=player, own_goal=False).count()
    own_goals = Goal.objects.filter(player=player, own_goal=True).count()

    return {
        "player_id": str(player.id),
        "name": player.name,
        "active": player.active,
        "matches_played": played,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_rate": round((wins / played) * 100, 2) if played else 0,
        "goals_for": goals_for,
        "own_goals": own_goals,
        "net_goals": goals_for - own_goals,
        "current_win_streak": current_streak,
        "best_win_streak": best_streak,
        "goals_per_match": round(goals_for / played, 2) if played else 0,
    }


def build_group_dashboard(group: FriendGroup) -> dict:
    matches = Match.objects.filter(group=group)
    total_matches = matches.count()

    score_goals = sum(match.score_a + match.score_b for match in matches.only("score_a", "score_b"))
    own_goals = Goal.objects.filter(match__group=group, own_goal=True).count()
    total_goals = max(score_goals - own_goals, 0)

    most_scored = (
        matches.annotate(total_goals=F("score_a") + F("score_b"))
        .order_by("-total_goals", "-played_at")
        .first()
    )
    last_match = matches.order_by("-played_at").first()

    players = list(group.players.all())
    player_stats = [build_player_stats(player) for player in players]

    top_scorer = max(player_stats, key=lambda item: item["goals_for"], default=None)
    own_goal_king = max(player_stats, key=lambda item: item["own_goals"], default=None)
    most_participative = max(player_stats, key=lambda item: item["matches_played"], default=None)
    active_streak_leader = max(player_stats, key=lambda item: item["current_win_streak"], default=None)
    win_rate_candidates = [item for item in player_stats if item["matches_played"] >= 5]
    best_win_rate = max(win_rate_candidates, key=lambda item: item["win_rate"], default=None)

    return {
        "group": {"id": str(group.id), "name": group.name, "code": group.code},
        "global": {
            "total_matches": total_matches,
            "total_goals": total_goals,
            "score_goals": score_goals,
            "own_goals": own_goals,
            "goals_per_match": round(total_goals / total_matches, 2) if total_matches else 0,
            "most_scored_match": _match_summary(most_scored),
            "last_match": _match_summary(last_match),
        },
        "rankings": {
            "top_scorer": top_scorer,
            "own_goal_king": own_goal_king,
            "most_participative": most_participative,
            "best_win_rate_min_5": best_win_rate,
            "active_streak_leader": active_streak_leader,
        },
        "players": player_stats,
    }
