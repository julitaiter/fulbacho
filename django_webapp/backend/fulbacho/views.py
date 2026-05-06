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
    build_goal_formset,
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


def _goal_initial(match: Match) -> list[dict]:
    return [
        {
            "team_scored_for": goal.team_scored_for,
            "player": goal.player_id,
            "own_goal": goal.own_goal,
        }
        for goal in match.goals.order_by("created_at")
    ]


def _roster_initial(match: Match) -> dict:
    team_a = []
    team_b = []
    for entry in match.match_players.select_related("player"):
        if entry.team == Team.A:
            team_a.append(entry.player_id)
        else:
            team_b.append(entry.player_id)
    return {"team_a_players": team_a, "team_b_players": team_b}


def _goals_from_formset(goal_formset) -> list[dict]:
    goals = []
    for goal_form in goal_formset:
        cleaned = goal_form.cleaned_data
        if not cleaned:
            continue
        if cleaned.get("DELETE"):
            continue
        team = cleaned.get("team_scored_for")
        player = cleaned.get("player")
        own_goal = cleaned.get("own_goal", False)
        if not team and not player and not own_goal:
            continue
        goals.append(
            {
                "team_scored_for": team,
                "player": player,
                "own_goal": own_goal,
            }
        )
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
    goal_formset = build_goal_formset(
        data=request.POST or None,
        player_queryset=active_players,
        initial=_goal_initial(match) if match else None,
    )

    if request.method == "POST":
        if match_form.is_valid() and roster_form.is_valid() and goal_formset.is_valid():
            data = {
                **match_form.cleaned_data,
                "group": group,
                "team_a_players": [player.id for player in roster_form.cleaned_data["team_a_players"]],
                "team_b_players": [player.id for player in roster_form.cleaned_data["team_b_players"]],
                "goals": _goals_from_formset(goal_formset),
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
            "goal_formset": goal_formset,
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
