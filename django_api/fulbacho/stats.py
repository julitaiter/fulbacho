from __future__ import annotations

from django.db.models import Count, F, Q

from .models import Goal, Group, Match, MatchPlayer, Player, Team


def match_total_goals(match: Match) -> int:
    return int(match.score_a or 0) + int(match.score_b or 0)


def match_winner(match: Match) -> str | None:
    if match.score_a == match.score_b:
        return None
    return Team.A if match.score_a > match.score_b else Team.B


def result_for_team(match: Match, team: str) -> str:
    winner = match_winner(match)
    if winner is None:
        return "draw"
    return "win" if winner == team else "loss"


def serialize_match(match: Match | None) -> dict | None:
    if not match:
        return None
    return {
        "id": str(match.id),
        "played_at": match.played_at.isoformat(),
        "modality": match.modality,
        "location": match.location,
        "team_a_name": match.team_a_name,
        "team_b_name": match.team_b_name,
        "score_a": match.score_a,
        "score_b": match.score_b,
        "total_goals": match_total_goals(match),
    }


def streaks_from_outcomes(outcomes: list[str]) -> tuple[int, int]:
    """Devuelve (racha_actual_de_victorias, mejor_racha_historica)."""

    current = 0
    for outcome in reversed(outcomes):
        if outcome == "win":
            current += 1
        else:
            break

    best = 0
    running = 0
    for outcome in outcomes:
        if outcome == "win":
            running += 1
            best = max(best, running)
        else:
            running = 0
    return current, best


def player_stats(player: Player) -> dict:
    entries = (
        MatchPlayer.objects.filter(player=player)
        .select_related("match")
        .order_by("match__played_at", "match__created_at")
    )

    outcomes: list[str] = []
    wins = losses = draws = 0
    for entry in entries:
        outcome = result_for_team(entry.match, entry.team)
        outcomes.append(outcome)
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1
        else:
            draws += 1

    matches_played = len(outcomes)
    goals_for = Goal.objects.filter(player=player, own_goal=False).count()
    own_goals = Goal.objects.filter(player=player, own_goal=True).count()
    current_streak, best_streak = streaks_from_outcomes(outcomes)

    return {
        "id": str(player.id),
        "name": player.name,
        "active": player.active,
        "matches_played": matches_played,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "win_pct": round((wins / matches_played) * 100, 2) if matches_played else 0,
        "goals_for": goals_for,
        "own_goals": own_goals,
        "net_goals": goals_for - own_goals,
        "current_win_streak": current_streak,
        "best_win_streak": best_streak,
        "goals_per_match": round(goals_for / matches_played, 2) if matches_played else 0,
    }


def top_players_by_stat(players: list[dict], key: str, limit: int = 10) -> list[dict]:
    return sorted(players, key=lambda item: (-item[key], item["name"].lower()))[:limit]


def group_dashboard(group: Group) -> dict:
    matches = Match.objects.filter(group=group)
    total_matches = matches.count()

    # Goles totales de la especificacion: goles a favor, sin contar goles en contra.
    total_goals = Goal.objects.filter(match__group=group, own_goal=False).count()
    avg_goals = round(total_goals / total_matches, 2) if total_matches else 0

    most_scored = (
        matches.annotate(total_goals=F("score_a") + F("score_b"))
        .order_by("-total_goals", "-played_at")
        .first()
    )
    last_match = matches.order_by("-played_at", "-created_at").first()

    players_qs = Player.objects.filter(group=group).annotate(
        matches_played=Count("match_entries", distinct=True),
        goals_for=Count("goals", filter=Q(goals__own_goal=False), distinct=True),
        own_goals_count=Count("goals", filter=Q(goals__own_goal=True), distinct=True),
    )

    player_rows = [player_stats(player) for player in players_qs]
    qualifying_win_pct = [row for row in player_rows if row["matches_played"] >= 5]

    return {
        "group": {
            "id": str(group.id),
            "name": group.name,
            "code": group.code,
        },
        "group_stats": {
            "total_matches": total_matches,
            "total_goals": total_goals,
            "avg_goals_per_match": avg_goals,
            "most_scored_match": serialize_match(most_scored),
            "last_match": serialize_match(last_match),
        },
        "rankings": {
            "top_scorers": top_players_by_stat(player_rows, "goals_for"),
            "own_goal_king": top_players_by_stat(player_rows, "own_goals"),
            "active_win_streak": top_players_by_stat(player_rows, "current_win_streak"),
            "most_participative": top_players_by_stat(player_rows, "matches_played"),
            "top_win_pct_min_5": top_players_by_stat(qualifying_win_pct, "win_pct"),
        },
        "players": player_rows,
    }
