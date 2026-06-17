from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .access import get_group_for_user, groups_for_user, is_group_admin
from .forms import (
    GuestCodeForm,
    GroupForm,
    JoinGroupForm,
    MatchForm,
    MatchRosterForm,
    PlayerForm,
    RegisterForm,
)
from .models import FriendGroup, Goal, GroupMember, Match, Player, Team
from .services import (
    build_group_dashboard,
    build_player_stats,
    create_group,
    create_match,
    join_group_by_code,
    replace_match,
)


def _validation_error_text(exc: ValidationError) -> str:
    try:
        message_dict = exc.message_dict
    except AttributeError:
        return " ".join(exc.messages)
    parts = []
    for field, errors in message_dict.items():
        parts.append(f"{field}: {', '.join(errors)}")
    return "; ".join(parts)


def _roster_initial(match: Match) -> dict:
    team_a = []
    team_b = []
    for entry in match.match_players.select_related("player"):
        if entry.team == Team.A:
            team_a.append(entry.player_id)
        else:
            team_b.append(entry.player_id)
    return {"team_a_players": team_a, "team_b_players": team_b}


def _goal_counts_initial(match: Match | None) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    if not match:
        return counts

    for goal in match.goals.select_related("player").order_by("created_at"):
        if not goal.player_id:
            continue
        player_key = str(goal.player_id)
        counts.setdefault(player_key, {"for": 0, "against": 0})
        if goal.own_goal:
            counts[player_key]["against"] += 1
        else:
            counts[player_key]["for"] += 1
    return counts


def _goal_counter_value(request, field_name: str, initial_count: int) -> str:
    if request.method == "POST":
        return request.POST.get(field_name, "0")
    return str(initial_count)


def _roster_rows(players, request, match: Match | None) -> list[dict]:
    initial_roster = _roster_initial(match) if match else {"team_a_players": [], "team_b_players": []}
    initial_counts = _goal_counts_initial(match)

    if request.method == "POST":
        selected_a = set(request.POST.getlist("team_a_players"))
        selected_b = set(request.POST.getlist("team_b_players"))
    else:
        selected_a = {str(player_id) for player_id in initial_roster["team_a_players"]}
        selected_b = {str(player_id) for player_id in initial_roster["team_b_players"]}

    rows = []
    for player in players:
        player_key = str(player.id)
        counts = initial_counts.get(player_key, {"for": 0, "against": 0})
        rows.append(
            {
                "player": player,
                "checked_a": player_key in selected_a,
                "checked_b": player_key in selected_b,
                "a_goals_for_name": f"goals_for_{Team.A}_{player.id}",
                "a_own_goals_name": f"own_goals_{Team.A}_{player.id}",
                "b_goals_for_name": f"goals_for_{Team.B}_{player.id}",
                "b_own_goals_name": f"own_goals_{Team.B}_{player.id}",
                "a_goals_for_value": _goal_counter_value(
                    request,
                    f"goals_for_{Team.A}_{player.id}",
                    counts["for"] if player_key in selected_a else 0,
                ),
                "a_own_goals_value": _goal_counter_value(
                    request,
                    f"own_goals_{Team.A}_{player.id}",
                    counts["against"] if player_key in selected_a else 0,
                ),
                "b_goals_for_value": _goal_counter_value(
                    request,
                    f"goals_for_{Team.B}_{player.id}",
                    counts["for"] if player_key in selected_b else 0,
                ),
                "b_own_goals_value": _goal_counter_value(
                    request,
                    f"own_goals_{Team.B}_{player.id}",
                    counts["against"] if player_key in selected_b else 0,
                ),
            }
        )
    return rows


def _parse_goal_counter(request, field_name: str, label: str) -> int:
    raw_value = (request.POST.get(field_name) or "0").strip()
    if raw_value == "":
        return 0
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValidationError(f"{label} debe ser un nÃºmero entero.") from exc
    if value < 0:
        raise ValidationError(f"{label} no puede ser negativo.")
    return value


def _goals_from_counter_inputs(request, roster_form: MatchRosterForm) -> list[dict]:
    goals = []
    team_configs = [
        (Team.A, Team.B, roster_form.cleaned_data["team_a_players"]),
        (Team.B, Team.A, roster_form.cleaned_data["team_b_players"]),
    ]

    for team, opponent, players in team_configs:
        for player in players:
            goals_for = _parse_goal_counter(
                request,
                f"goals_for_{team}_{player.id}",
                f"Goles a favor de {player.name}",
            )
            own_goals = _parse_goal_counter(
                request,
                f"own_goals_{team}_{player.id}",
                f"Goles en contra de {player.name}",
            )
            goals.extend({"team_scored_for": team, "player": player, "own_goal": False} for _ in range(goals_for))
            goals.extend({"team_scored_for": opponent, "player": player, "own_goal": True} for _ in range(own_goals))
    return goals


def _warn_unassigned_goals(request, match: Match) -> None:
    loaded_goals = match.goals.count()
    missing = match.score_a + match.score_b - loaded_goals
    if missing > 0:
        messages.warning(
            request,
            f"El partido se guardó. Quedaron {missing} goles del marcador sin asignar a jugadores.",
        )


def landing(request):
    if request.user.is_authenticated:
        return redirect("groups-index")
    return render(request, "fulbacho/landing.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("groups-index")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Cuenta creada. Ya podés crear o unirte a un grupo.")
        return redirect("groups-index")

    return render(request, "fulbacho/register.html", {"form": form})


@login_required
def groups_index(request):
    groups = (
        groups_for_user(request.user)
        .annotate(players_count=Count("players", distinct=True), matches_count=Count("matches", distinct=True))
        .order_by("name")
    )
    return render(request, "fulbacho/groups/index.html", {"groups": groups})


@login_required
def group_create(request):
    form = GroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        group = create_group(user=request.user, name=form.cleaned_data["name"])
        messages.success(request, f"Grupo creado. Código: {group.code}")
        return redirect("group-dashboard", group_id=group.id)
    return render(request, "fulbacho/groups/form.html", {"form": form, "title": "Crear grupo"})


@login_required
def group_join(request):
    form = JoinGroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            group = join_group_by_code(user=request.user, code=form.cleaned_data["code"])
        except ValidationError as exc:
            form.add_error("code", _validation_error_text(exc))
        else:
            messages.success(request, f"Te uniste a {group.name}.")
            return redirect("group-dashboard", group_id=group.id)

    return render(request, "fulbacho/groups/join.html", {"form": form})


@login_required
def group_dashboard(request, group_id):
    group = get_group_for_user(request.user, group_id)
    dashboard = build_group_dashboard(group)
    return render(
        request,
        "fulbacho/dashboard.html",
        {
            "group": group,
            "dashboard": dashboard,
            "guest_mode": False,
            "active_tab": "dashboard",
            "is_admin": is_group_admin(request.user, group),
        },
    )


@login_required
def group_settings(request, group_id):
    group = get_group_for_user(request.user, group_id)
    admin = is_group_admin(request.user, group)
    form = GroupForm(request.POST or None, instance=group)

    if request.method == "POST":
        if not admin:
            raise PermissionDenied("Solo un admin puede modificar el grupo.")
        if form.is_valid():
            form.save()
            messages.success(request, "Grupo actualizado.")
            return redirect("group-settings", group_id=group.id)

    members = GroupMember.objects.filter(group=group).select_related("user").order_by("joined_at")
    return render(
        request,
        "fulbacho/groups/settings.html",
        {
            "group": group,
            "form": form,
            "members": members,
            "is_admin": admin,
            "active_tab": "settings",
        },
    )


@login_required
def players_list(request, group_id):
    group = get_group_for_user(request.user, group_id)
    players = group.players.filter(active=True).order_by("name")
    player_stats = [build_player_stats(player) for player in players]
    return render(
        request,
        "fulbacho/players/list.html",
        {
            "group": group,
            "players": players,
            "player_stats": player_stats,
            "guest_mode": False,
            "active_tab": "players",
        },
    )


@login_required
def player_create(request, group_id):
    group = get_group_for_user(request.user, group_id)
    form = PlayerForm(request.POST or None, group=group)
    if request.method == "POST" and form.is_valid():
        player = form.save(commit=False)
        player.group = group
        player.save()
        messages.success(request, f"Jugador agregado: {player.name}.")
        return redirect("players-list", group_id=group.id)

    return render(
        request,
        "fulbacho/players/form.html",
        {"group": group, "form": form, "title": "Nuevo jugador", "active_tab": "players"},
    )


@login_required
def player_detail(request, group_id, player_id):
    group = get_group_for_user(request.user, group_id)
    player = get_object_or_404(Player, id=player_id, group=group)
    stats = build_player_stats(player)
    appearances = (
        player.match_players.select_related("match")
        .prefetch_related("match__goals", "match__match_players")
        .order_by("-match__played_at")[:20]
    )
    return render(
        request,
        "fulbacho/players/detail.html",
        {
            "group": group,
            "player": player,
            "stats": stats,
            "appearances": appearances,
            "guest_mode": False,
            "active_tab": "players",
        },
    )


@login_required
@require_POST
def player_deactivate(request, group_id, player_id):
    group = get_group_for_user(request.user, group_id)
    player = get_object_or_404(Player, id=player_id, group=group)
    player.active = False
    player.save(update_fields=["active", "updated_at"])
    messages.success(request, f"{player.name} fue dado de baja. Sus estadísticas se conservan.")
    return redirect("players-list", group_id=group.id)


@login_required
def matches_list(request, group_id):
    group = get_group_for_user(request.user, group_id)
    matches = (
        group.matches.select_related("created_by")
        .prefetch_related("match_players__player", "goals__player")
        .order_by("-played_at")
    )
    return render(
        request,
        "fulbacho/matches/list.html",
        {
            "group": group,
            "matches": matches,
            "guest_mode": False,
            "active_tab": "matches",
        },
    )


@login_required
def match_detail(request, group_id, match_id):
    group = get_group_for_user(request.user, group_id)
    match = get_object_or_404(
        Match.objects.prefetch_related("match_players__player", "goals__player"),
        id=match_id,
        group=group,
    )
    return render(
        request,
        "fulbacho/matches/detail.html",
        {
            "group": group,
            "match": match,
            "guest_mode": False,
            "active_tab": "matches",
        },
    )


def _match_editor(request, group: FriendGroup, match: Match | None = None):
    if match:
        active_players = (
            group.players.filter(Q(active=True) | Q(match_players__match=match))
            .distinct()
            .order_by("name")
        )
    else:
        active_players = group.players.filter(active=True).order_by("name")
    match_form = MatchForm(request.POST or None, instance=match)
    roster_form = MatchRosterForm(
        request.POST or None,
        player_queryset=active_players,
        initial=_roster_initial(match) if match else None,
    )

    if request.method == "POST":
        if match_form.is_valid() and roster_form.is_valid():
            try:
                goals = _goals_from_counter_inputs(request, roster_form)
            except ValidationError as exc:
                match_form.add_error(None, _validation_error_text(exc))
                goals = None
        else:
            goals = None

        if goals is not None:
            data = {
                **match_form.cleaned_data,
                "group": group,
                "team_a_players": [player.id for player in roster_form.cleaned_data["team_a_players"]],
                "team_b_players": [player.id for player in roster_form.cleaned_data["team_b_players"]],
                "goals": goals,
            }
            try:
                if match:
                    saved_match = replace_match(match=match, user=request.user, validated_data=data)
                    messages.success(request, "Partido actualizado.")
                else:
                    saved_match = create_match(created_by=request.user, validated_data=data)
                    messages.success(request, "Partido guardado.")
                _warn_unassigned_goals(request, saved_match)
                return redirect("match-detail", group_id=group.id, match_id=saved_match.id)
            except ValidationError as exc:
                match_form.add_error(None, _validation_error_text(exc))

    return render(
        request,
        "fulbacho/matches/form.html",
        {
            "group": group,
            "match": match,
            "match_form": match_form,
            "roster_form": roster_form,
            "roster_rows": _roster_rows(active_players, request, match),
            "players_count": active_players.count(),
            "title": "Editar partido" if match else "Nuevo partido",
            "active_tab": "matches",
        },
    )


@login_required
def match_create(request, group_id):
    group = get_group_for_user(request.user, group_id)
    return _match_editor(request, group)


@login_required
def match_edit(request, group_id, match_id):
    group = get_group_for_user(request.user, group_id)
    match = get_object_or_404(Match, id=match_id, group=group)
    if not match.can_be_edited:
        messages.error(request, "Este partido ya no se puede editar: pasaron más de 24 horas.")
        return redirect("match-detail", group_id=group.id, match_id=match.id)
    return _match_editor(request, group, match=match)


def guest_code(request):
    form = GuestCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["code"]
        if FriendGroup.objects.filter(code=code).exists():
            return redirect("guest-dashboard", code=code)
        form.add_error("code", "No existe un grupo con ese código.")

    return render(request, "fulbacho/guest/code_form.html", {"form": form, "guest_mode": True})


def _guest_group(code: str) -> FriendGroup:
    return get_object_or_404(FriendGroup, code=code.strip().upper())


def guest_dashboard(request, code):
    group = _guest_group(code)
    dashboard = build_group_dashboard(group)
    return render(
        request,
        "fulbacho/dashboard.html",
        {
            "group": group,
            "dashboard": dashboard,
            "guest_mode": True,
            "active_tab": "dashboard",
        },
    )


def guest_players(request, code):
    group = _guest_group(code)
    players = group.players.filter(active=True).order_by("name")
    player_stats = [build_player_stats(player) for player in players]
    return render(
        request,
        "fulbacho/players/list.html",
        {
            "group": group,
            "players": players,
            "player_stats": player_stats,
            "guest_mode": True,
            "active_tab": "players",
        },
    )


def guest_player_detail(request, code, player_id):
    group = _guest_group(code)
    player = get_object_or_404(Player, id=player_id, group=group, active=True)
    stats = build_player_stats(player)
    appearances = player.match_players.select_related("match").order_by("-match__played_at")[:20]
    return render(
        request,
        "fulbacho/players/detail.html",
        {
            "group": group,
            "player": player,
            "stats": stats,
            "appearances": appearances,
            "guest_mode": True,
            "active_tab": "players",
        },
    )


def guest_matches(request, code):
    group = _guest_group(code)
    matches = (
        group.matches.prefetch_related("match_players__player", "goals__player")
        .order_by("-played_at")
    )
    return render(
        request,
        "fulbacho/matches/list.html",
        {
            "group": group,
            "matches": matches,
            "guest_mode": True,
            "active_tab": "matches",
        },
    )


def guest_match_detail(request, code, match_id):
    group = _guest_group(code)
    match = get_object_or_404(
        Match.objects.prefetch_related("match_players__player", "goals__player"),
        id=match_id,
        group=group,
    )
    return render(
        request,
        "fulbacho/matches/detail.html",
        {
            "group": group,
            "match": match,
            "guest_mode": True,
            "active_tab": "matches",
        },
    )
