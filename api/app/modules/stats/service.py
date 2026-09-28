from math import floor
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.models import User
from app.modules.groups.permissions import require_member
from app.modules.matches.models import Goal, Match, MatchParticipant, TeamSide
from app.modules.players.models import Player


def minimum_matches_for_win_rate(total_group_matches: int) -> int:
    if total_group_matches <= 5:
        return 1
    if total_group_matches <= 15:
        return max(floor(total_group_matches * 0.25), 2)
    return 5


def _scores_by_match(db: Session, match_ids: list[UUID]):
    if not match_ids:
        return {}
    rows = db.execute(
        select(Goal.match_id, Goal.team_scored_for, func.count(Goal.id))
        .where(Goal.match_id.in_(match_ids))
        .group_by(Goal.match_id, Goal.team_scored_for)
    ).all()
    result = {match_id: {TeamSide.A: 0, TeamSide.B: 0} for match_id in match_ids}
    for match_id, team, count in rows:
        result[match_id][team] = count
    return result


def _player_stats(db: Session, group_id: UUID):
    players = list(db.scalars(select(Player).where(Player.group_id == group_id).order_by(Player.name)))
    total_group_matches = db.scalar(select(func.count()).select_from(Match).where(Match.group_id == group_id)) or 0
    minimum = minimum_matches_for_win_rate(total_group_matches)
    stats = []

    for player in players:
        entries = db.execute(
            select(MatchParticipant, Match)
            .join(Match, Match.id == MatchParticipant.match_id)
            .where(MatchParticipant.player_id == player.id)
            .order_by(Match.played_at, Match.created_at)
        ).all()
        match_ids = [match.id for _, match in entries]
        scores = _scores_by_match(db, match_ids)
        wins = losses = draws = 0
        results = []
        for participant, match in entries:
            match_scores = scores.get(match.id, {TeamSide.A: 0, TeamSide.B: 0})
            own = match_scores[participant.team]
            other = match_scores[TeamSide.other(participant.team)]
            if own > other:
                result = "win"
                wins += 1
            elif own < other:
                result = "loss"
                losses += 1
            else:
                result = "draw"
                draws += 1
            results.append(result)

        current = 0
        for result in reversed(results):
            if result == "win":
                current += 1
            else:
                break
        best = run = 0
        for result in results:
            if result == "win":
                run += 1
                best = max(best, run)
            else:
                run = 0

        goals_for = db.scalar(
            select(func.count())
            .select_from(Goal)
            .join(MatchParticipant, MatchParticipant.id == Goal.participant_id)
            .where(MatchParticipant.player_id == player.id, Goal.own_goal.is_(False))
        ) or 0
        own_goals = db.scalar(
            select(func.count())
            .select_from(Goal)
            .join(MatchParticipant, MatchParticipant.id == Goal.participant_id)
            .where(MatchParticipant.player_id == player.id, Goal.own_goal.is_(True))
        ) or 0
        played = len(entries)
        stats.append(
            {
                "player_id": player.id,
                "name": player.name,
                "active": player.active,
                "matches_played": played,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": round((wins / played) * 100, 2) if played else 0.0,
                "goals_for": goals_for,
                "own_goals": own_goals,
                "net_goals": goals_for - own_goals,
                "current_win_streak": current,
                "best_win_streak": best,
                "goals_per_match": round(goals_for / played, 2) if played else 0.0,
                "eligible_for_win_rate_ranking": played >= minimum,
            }
        )
    return stats, minimum


def get_summary(db: Session, group_id: UUID, user: User | None = None):
    if user is not None:
        require_member(db, group_id, user)
    matches = list(db.scalars(select(Match).where(Match.group_id == group_id).order_by(Match.played_at.desc())))
    total_matches = len(matches)
    total_goals = db.scalar(
        select(func.count()).select_from(Goal).join(Match, Match.id == Goal.match_id).where(Match.group_id == group_id)
    ) or 0
    total_own_goals = db.scalar(
        select(func.count())
        .select_from(Goal)
        .join(Match, Match.id == Goal.match_id)
        .where(Match.group_id == group_id, Goal.own_goal.is_(True))
    ) or 0
    scores = _scores_by_match(db, [match.id for match in matches])

    def brief(match):
        if not match:
            return None
        match_scores = scores.get(match.id, {TeamSide.A: 0, TeamSide.B: 0})
        return {
            "id": match.id,
            "played_at": match.played_at,
            "team_a_name": match.team_a_name,
            "team_b_name": match.team_b_name,
            "score_a": match_scores[TeamSide.A],
            "score_b": match_scores[TeamSide.B],
        }

    most_scored = None
    if matches:
        most_scored = max(matches, key=lambda m: scores.get(m.id, {TeamSide.A: 0, TeamSide.B: 0})[TeamSide.A] + scores.get(m.id, {TeamSide.A: 0, TeamSide.B: 0})[TeamSide.B])
    return {
        "total_matches": total_matches,
        "total_goals": total_goals,
        "total_own_goals": total_own_goals,
        "goals_per_match": round(total_goals / total_matches, 2) if total_matches else 0.0,
        "most_scored_match": brief(most_scored),
        "last_match": brief(matches[0] if matches else None),
    }



def get_all_player_stats(db: Session, group_id: UUID, user: User | None = None):
    if user is not None:
        require_member(db, group_id, user)
    stats, _ = _player_stats(db, group_id)
    return stats

def get_player_stats(db: Session, group_id: UUID, player_id: UUID, user: User | None = None):
    if user is not None:
        require_member(db, group_id, user)
    stats, _ = _player_stats(db, group_id)
    for item in stats:
        if item["player_id"] == player_id:
            return item
    return None


def get_rankings(db: Session, group_id: UUID, user: User | None = None, limit: int = 10):
    if user is not None:
        require_member(db, group_id, user)
    stats, minimum = _player_stats(db, group_id)
    eligible = [s for s in stats if s["eligible_for_win_rate_ranking"]]
    return {
        "minimum_matches_for_win_rate": minimum,
        "top_scorers": sorted(stats, key=lambda s: (-s["goals_for"], s["name"].lower()))[:limit],
        "own_goal_kings": sorted(stats, key=lambda s: (-s["own_goals"], s["name"].lower()))[:limit],
        "most_participative": sorted(stats, key=lambda s: (-s["matches_played"], s["name"].lower()))[:limit],
        "active_streaks": sorted(stats, key=lambda s: (-s["current_win_streak"], s["name"].lower()))[:limit],
        "best_win_rate": sorted(eligible, key=lambda s: (-s["win_rate"], -s["matches_played"], s["name"].lower()))[:limit],
    }
