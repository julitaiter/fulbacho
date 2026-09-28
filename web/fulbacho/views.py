import csv
import io
import json
import re
from collections import defaultdict
from datetime import datetime

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .api_client import ApiError, api_for
from .auth import api_login_required
from .forms import (
    AttachCasualForm,
    CsvImportForm,
    GroupForm,
    GuestCodeForm,
    JoinGroupForm,
    LoginForm,
    MatchForm,
    MemberRoleForm,
    PlayerForm,
    PromoteCasualForm,
    RegisterForm,
)


def _safe_next(request, default="groups-index"):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return reverse(default)


def _api_message(exc: ApiError) -> str:
    return exc.detail or "Ocurrió un error al comunicarse con la API."


def _is_admin(request, members: list[dict]) -> bool:
    user_id = str(request.user.id)
    return any(str(member["user_id"]) == user_id and member["role"] == "admin" for member in members)


def _match_brief_total_goals(match: dict | None):
    if match:
        match["total_goals"] = int(match.get("score_a", 0)) + int(match.get("score_b", 0))
    return match


def _ranking_highlight(items, metric):
    if not items:
        return None
    leader_value = items[0].get(metric)
    leaders = [item for item in items if item.get(metric) == leader_value]
    highlight = dict(items[0])
    if len(leaders) == 1:
        highlight["display_name"] = leaders[0]["name"]
    elif len(leaders) == 2:
        highlight["display_name"] = f"{leaders[0]['name']} y {leaders[1]['name']}"
    else:
        highlight["display_name"] = f"{len(leaders)} personas"
    highlight["leaders_count"] = len(leaders)
    return highlight

def _dashboard(api, group_id=None, code=None):
    if group_id:
        summary = api.stats.summary(group_id)
        rankings = api.stats.rankings(group_id, limit=100)
        players = api.stats.players(group_id)
    else:
        summary = api.guest.summary(code)
        rankings = api.guest.rankings(code, limit=100)
        players = api.guest.player_stats_list(code)

    summary["most_scored_match"] = _match_brief_total_goals(summary.get("most_scored_match"))
    summary["last_match"] = _match_brief_total_goals(summary.get("last_match"))
    return {
        "global": summary,
        "rankings": {
            "top_scorer": _ranking_highlight(rankings.get("top_scorers"), "goals_for"),
            "own_goal_king": _ranking_highlight(rankings.get("own_goal_kings"), "own_goals"),
            "most_participative": _ranking_highlight(
                rankings.get("most_participative"), "matches_played"
            ),
            "best_win_rate": _ranking_highlight(rankings.get("best_win_rate"), "win_rate"),
            "active_streak_leader": _ranking_highlight(
                rankings.get("active_streaks"), "current_win_streak"
            ),
            "minimum_matches_for_win_rate": rankings.get("minimum_matches_for_win_rate", 1),
        },
        "players": players,
    }


def _score_goal_counts(match: dict):
    counts = defaultdict(lambda: {"goals_for": 0, "own_goals": 0})
    for goal in match.get("goals", []):
        participant_id = goal.get("participant_id")
        if not participant_id:
            continue
        key = str(participant_id)
        if goal.get("own_goal"):
            counts[key]["own_goals"] += 1
        else:
            counts[key]["goals_for"] += 1
    return counts


def _team_summaries(match: dict):
    counts = _score_goal_counts(match)
    summaries = {"A": [], "B": []}
    for participant in match.get("participants", []):
        item_counts = counts[str(participant["id"])]
        summaries[participant["team"]].append(
            {
                "id": participant["id"],
                "player_id": participant.get("player_id"),
                "name": participant["display_name"],
                "casual": participant.get("player_id") is None,
                **item_counts,
            }
        )
    for side in summaries:
        summaries[side].sort(key=lambda item: item["name"].lower())
    return summaries


def _appearance_rows(matches: list[dict], player_id: str):
    rows = []
    for match in matches:
        participant = next(
            (p for p in match.get("participants", []) if str(p.get("player_id")) == str(player_id)),
            None,
        )
        if not participant:
            continue
        side = participant["team"]
        own_score = match["score_a"] if side == "A" else match["score_b"]
        other_score = match["score_b"] if side == "A" else match["score_a"]
        result = "Empate" if own_score == other_score else ("Victoria" if own_score > other_score else "Derrota")
        rows.append(
            {
                "match": match,
                "team": side,
                "team_name": match["team_a_name"] if side == "A" else match["team_b_name"],
                "result": result,
            }
        )
    return rows


def _all_matches(api, group_id):
    rows = []
    offset = 0
    while True:
        page = api.matches.list(group_id, offset=offset, limit=100)
        rows.extend(page)
        if len(page) < 100:
            return rows
        offset += 100


def _csv_response(filename: str, fieldnames: list[str], rows: list[dict]):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write("\ufeff")
    writer = csv.DictWriter(response, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return response


def _read_csv_upload(uploaded_file):
    try:
        content = uploaded_file.read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("El CSV debe estar codificado en UTF-8.") from exc
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError("El CSV no tiene encabezados.")
    return list(reader), set(reader.fieldnames)


def _csv_bool(value, default=True):
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in {"1", "true", "si", "sí", "yes", "y"}


def landing(request):
    if request.user.is_authenticated:
        return redirect("groups-index")
    return render(request, "fulbacho/landing.html")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("groups-index")
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        api = api_for(request)
        try:
            payload = api.auth.login(**form.cleaned_data)
        except ApiError as exc:
            form.add_error(None, _api_message(exc))
        else:
            api.client.store_auth(payload)
            messages.success(request, f"Bienvenido, {payload['user']['display_name']}.")
            return redirect(_safe_next(request))
    return render(request, "registration/login.html", {"form": form, "next": request.POST.get("next") or request.GET.get("next", "")})


def register(request):
    if request.user.is_authenticated:
        return redirect("groups-index")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        api = api_for(request)
        try:
            payload = api.auth.register(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
                display_name=form.cleaned_data["display_name"],
            )
        except ApiError as exc:
            form.add_error(None, _api_message(exc))
        else:
            api.client.store_auth(payload)
            messages.success(request, "Cuenta creada. Ya podés crear o unirte a un grupo.")
            return redirect("groups-index")
    return render(request, "fulbacho/register.html", {"form": form})


@require_POST
def logout_view(request):
    api = api_for(request)
    refresh = request.session.get("refresh_token")
    if refresh:
        try:
            api.auth.logout(refresh)
        except ApiError:
            pass
    request.session.flush()
    return redirect("landing")


@api_login_required
def groups_index(request):
    api = api_for(request)
    try:
        groups = api.groups.overview()
    except ApiError as exc:
        if exc.status_code == 401:
            return redirect("login")
        messages.error(request, _api_message(exc))
        groups = []
    return render(request, "fulbacho/groups/index.html", {"groups": groups})


@api_login_required
def group_create(request):
    form = GroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            group = api_for(request).groups.create(form.cleaned_data["name"])
        except ApiError as exc:
            form.add_error(None, _api_message(exc))
        else:
            messages.success(request, f"Grupo creado. Código: {group['code']}")
            return redirect("group-dashboard", group_id=group["id"])
    return render(request, "fulbacho/groups/form.html", {"form": form, "title": "Crear grupo"})


@api_login_required
def group_join(request):
    form = JoinGroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            group = api_for(request).groups.join(form.cleaned_data["code"])
        except ApiError as exc:
            form.add_error("code", _api_message(exc))
        else:
            messages.success(request, f"Te uniste a {group['name']}.")
            return redirect("group-dashboard", group_id=group["id"])
    return render(request, "fulbacho/groups/join.html", {"form": form})


@api_login_required
def group_dashboard(request, group_id):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
        members = api.groups.members(group_id)
        dashboard = _dashboard(api, group_id=group_id)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("groups-index")
    return render(
        request,
        "fulbacho/dashboard.html",
        {
            "group": group,
            "dashboard": dashboard,
            "guest_mode": False,
            "active_tab": "dashboard",
            "is_admin": _is_admin(request, members),
        },
    )


@api_login_required
def group_settings(request, group_id):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
        members = api.groups.members(group_id)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("groups-index")
    admin = _is_admin(request, members)
    form = GroupForm(request.POST or None, initial={"name": group["name"]})
    if request.method == "POST":
        if not admin:
            messages.error(request, "Solo un admin puede modificar el grupo.")
        elif form.is_valid():
            try:
                group = api.groups.update(group_id, form.cleaned_data["name"])
            except ApiError as exc:
                form.add_error(None, _api_message(exc))
            else:
                messages.success(request, "Grupo actualizado.")
                return redirect("group-settings", group_id=group_id)
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


@api_login_required
@require_POST
def member_role_update(request, group_id, user_id):
    form = MemberRoleForm(request.POST)
    if form.is_valid():
        try:
            api_for(request).groups.set_member_role(group_id, user_id, form.cleaned_data["role"])
            messages.success(request, "Rol actualizado.")
        except ApiError as exc:
            messages.error(request, _api_message(exc))
    return redirect("group-settings", group_id=group_id)


@api_login_required
@require_POST
def member_remove(request, group_id, user_id):
    try:
        api_for(request).groups.remove_member(group_id, user_id)
        messages.success(request, "Miembro eliminado del grupo.")
    except ApiError as exc:
        messages.error(request, _api_message(exc))
    return redirect("group-settings", group_id=group_id)


@api_login_required
def players_list(request, group_id):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
        players = api.players.list(group_id)
        stats = api.stats.players(group_id)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("groups-index")
    stats_by_id = {str(item["player_id"]): item for item in stats}
    player_stats = [stats_by_id.get(str(player["id"]), {"player_id": player["id"], "name": player["name"]}) for player in players]
    return render(request, "fulbacho/players/list.html", {"group": group, "players": players, "player_stats": player_stats, "guest_mode": False, "active_tab": "players"})


@api_login_required
def players_export_csv(request, group_id):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
        players = api.players.list(group_id, include_inactive=True)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("players-list", group_id=group_id)
    rows = [
        {
            "id": player["id"],
            "name": player["name"],
            "active": "1" if player["active"] else "0",
            "linked_user_id": player.get("linked_user_id") or "",
        }
        for player in players
    ]
    return _csv_response(f"fulbacho-{group['code']}-jugadores.csv", ["id", "name", "active", "linked_user_id"], rows)


@api_login_required
def players_import_csv(request, group_id):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("groups-index")
    form = CsvImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            rows, columns = _read_csv_upload(form.cleaned_data["file"])
            if "name" not in columns:
                raise ValueError("El CSV debe incluir la columna name.")
            imported = 0
            for row_number, row in enumerate(rows, start=2):
                name = (row.get("name") or "").strip()
                if not name:
                    raise ValueError(f"Fila {row_number}: name es obligatorio.")
                player_id = (row.get("id") or "").strip()
                payload = {
                    "name": name,
                    "linked_user_id": (row.get("linked_user_id") or "").strip() or None,
                    "active": _csv_bool(row.get("active"), True),
                }
                if player_id:
                    try:
                        api.players.get(group_id, player_id)
                    except ApiError as exc:
                        if exc.status_code != 404:
                            raise
                        created = api.players.create(group_id, {"name": name, "linked_user_id": payload["linked_user_id"]})
                        if not payload["active"]:
                            api.players.update(group_id, created["id"], {"active": False})
                    else:
                        api.players.update(group_id, player_id, payload)
                else:
                    created = api.players.create(group_id, {"name": name, "linked_user_id": payload["linked_user_id"]})
                    if not payload["active"]:
                        api.players.update(group_id, created["id"], {"active": False})
                imported += 1
        except (ValueError, ApiError) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else _api_message(exc))
        else:
            messages.success(request, f"Se importaron {imported} jugadores a través de la API.")
            return redirect("players-list", group_id=group_id)
    return render(request, "fulbacho/import_csv.html", {
        "group": group,
        "form": form,
        "title": "Importar jugadores",
        "description": "Columnas: name (obligatoria), id, active y linked_user_id (opcionales). Si id existe se actualiza; si no, se crea un jugador nuevo.",
        "cancel_url": reverse("players-list", args=[group_id]),
        "active_tab": "players",
    })


@api_login_required
def player_create(request, group_id):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
        members = api.groups.members(group_id)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("groups-index")
    form = PlayerForm(request.POST or None, members=members)
    if request.method == "POST" and form.is_valid():
        payload = {
            "name": form.cleaned_data["name"],
            "linked_user_id": form.cleaned_data["linked_user_id"] or None,
        }
        try:
            player = api.players.create(group_id, payload)
        except ApiError as exc:
            form.add_error(None, _api_message(exc))
        else:
            messages.success(request, f"Jugador agregado: {player['name']}.")
            return redirect("players-list", group_id=group_id)
    return render(request, "fulbacho/players/form.html", {"group": group, "form": form, "title": "Nuevo jugador", "active_tab": "players"})


@api_login_required
def player_edit(request, group_id, player_id):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
        player = api.players.get(group_id, player_id)
        members = api.groups.members(group_id)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("players-list", group_id=group_id)
    form = PlayerForm(
        request.POST or None,
        members=members,
        current_linked_user_id=player.get("linked_user_id"),
        initial={"name": player["name"]},
    )
    if request.method == "POST" and form.is_valid():
        try:
            player = api.players.update(
                group_id,
                player_id,
                {"name": form.cleaned_data["name"], "linked_user_id": form.cleaned_data["linked_user_id"] or None},
            )
        except ApiError as exc:
            form.add_error(None, _api_message(exc))
        else:
            messages.success(request, "Jugador actualizado.")
            return redirect("player-detail", group_id=group_id, player_id=player_id)
    return render(request, "fulbacho/players/form.html", {"group": group, "player": player, "form": form, "title": "Editar jugador", "active_tab": "players"})


@api_login_required
def player_detail(request, group_id, player_id):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
        player = api.players.get(group_id, player_id)
        stats = api.stats.player(group_id, player_id)
        matches = api.matches.list(group_id, player_id=player_id, limit=20)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("players-list", group_id=group_id)
    return render(
        request,
        "fulbacho/players/detail.html",
        {"group": group, "player": player, "stats": stats, "appearances": _appearance_rows(matches, str(player_id)), "guest_mode": False, "active_tab": "players"},
    )


@api_login_required
@require_POST
def player_deactivate(request, group_id, player_id):
    try:
        player = api_for(request).players.get(group_id, player_id)
        api_for(request).players.deactivate(group_id, player_id)
        messages.success(request, f"{player['name']} fue dado de baja. Sus estadísticas se conservan.")
    except ApiError as exc:
        messages.error(request, _api_message(exc))
    return redirect("players-list", group_id=group_id)


@api_login_required
def casuals_manage(request, group_id):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
        casuals = api.players.casuals(group_id)
        players = api.players.list(group_id)
        members = api.groups.members(group_id)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("players-list", group_id=group_id)

    promote_form = PromoteCasualForm(prefix="promote", casuals=casuals, members=members)
    attach_form = AttachCasualForm(prefix="attach", casuals=casuals, players=players)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "promote":
            promote_form = PromoteCasualForm(request.POST, prefix="promote", casuals=casuals, members=members)
            if promote_form.is_valid():
                payload = {
                    "name": promote_form.cleaned_data["name"],
                    "participant_ids": promote_form.cleaned_data["participant_ids"],
                    "linked_user_id": promote_form.cleaned_data["linked_user_id"] or None,
                }
                try:
                    player = api.players.promote_casual(group_id, payload)
                except ApiError as exc:
                    promote_form.add_error(None, _api_message(exc))
                else:
                    messages.success(request, f"{player['name']} ahora es jugador habitual y conserva las participaciones seleccionadas.")
                    return redirect("casuals-manage", group_id=group_id)
        elif action == "attach":
            attach_form = AttachCasualForm(request.POST, prefix="attach", casuals=casuals, players=players)
            if attach_form.is_valid():
                try:
                    api.players.attach_casual(group_id, attach_form.cleaned_data["player_id"], attach_form.cleaned_data["participant_ids"])
                except ApiError as exc:
                    attach_form.add_error(None, _api_message(exc))
                else:
                    messages.success(request, "Participaciones casuales vinculadas al jugador.")
                    return redirect("casuals-manage", group_id=group_id)

    return render(request, "fulbacho/players/casuals.html", {"group": group, "casuals": casuals, "promote_form": promote_form, "attach_form": attach_form, "active_tab": "players"})


def _initial_match_form(match):
    played_value = match["played_at"]
    played = (
        played_value
        if isinstance(played_value, datetime)
        else parse_datetime(played_value)
    )
    if played and timezone.is_aware(played):
        played = timezone.localtime(played)
    return {
        "played_at": (
            played.strftime("%Y-%m-%dT%H:%M")
            if isinstance(played, datetime)
            else str(played_value)[:16]
        ),
        "players_per_team": match["players_per_team"],
        "location": match.get("location") or "",
        "team_a_name": match["team_a_name"],
        "team_b_name": match["team_b_name"],
        "score_a": match["score_a"],
        "score_b": match["score_b"],
    }


def _participant_editor_rows(players, request, match=None, minimum=5):
    goal_counts = _score_goal_counts(match) if match else {}
    rows = {"A": [], "B": []}
    if match:
        for participant in match.get("participants", []):
            counts = goal_counts.get(str(participant["id"]), {"goals_for": 0, "own_goals": 0})
            side = participant["team"]
            rows[side].append(
                {
                    "name": participant["display_name"],
                    "player_id": str(participant.get("player_id") or ""),
                    **counts,
                }
            )

    if request.method == "POST":
        rows = {"A": [], "B": []}
        pattern = re.compile(r"^participant_([AB])_name_(\d+)$")
        found = []
        for key in request.POST.keys():
            match_key = pattern.match(key)
            if match_key:
                found.append((match_key.group(1), int(match_key.group(2))))
        for side, idx in sorted(set(found), key=lambda item: (item[0], item[1])):
            rows[side].append(
                {
                    "name": request.POST.get(f"participant_{side}_name_{idx}", ""),
                    "player_id": request.POST.get(f"participant_{side}_player_id_{idx}", ""),
                    "goals_for": request.POST.get(f"participant_{side}_goals_{idx}", "0"),
                    "own_goals": request.POST.get(f"participant_{side}_own_goals_{idx}", "0"),
                    "index": idx,
                }
            )
    else:
        for side in ("A", "B"):
            for idx, item in enumerate(rows[side]):
                item["index"] = idx

    for side in ("A", "B"):
        next_index = max((item.get("index", -1) for item in rows[side]), default=-1) + 1
        while len(rows[side]) < minimum:
            rows[side].append(
                {
                    "index": next_index,
                    "name": "",
                    "player_id": "",
                    "goals_for": 0,
                    "own_goals": 0,
                }
            )
            next_index += 1
    return rows

def _nonnegative_int(value, label):
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} debe ser un número entero.") from exc
    if parsed < 0:
        raise ValueError(f"{label} no puede ser negativo.")
    return parsed


def _build_match_payload(request, form, players):
    participants = {"A": [], "B": []}
    goals = []
    players_by_id = {str(player["id"]): player for player in players}
    used_player_ids = set()

    pattern = re.compile(r"^participant_([AB])_name_(\d+)$")
    found = []
    for key in request.POST.keys():
        match_key = pattern.match(key)
        if match_key:
            found.append((match_key.group(1), int(match_key.group(2))))
    for side, idx in sorted(set(found), key=lambda item: (item[0], item[1])):
        raw_name = request.POST.get(f"participant_{side}_name_{idx}") or ""
        name = raw_name.strip()
        if not name:
            continue
        submitted_player_id = request.POST.get(f"participant_{side}_player_id_{idx}") or ""
        player = players_by_id.get(submitted_player_id)
        if player and raw_name == player["name"]:
            if submitted_player_id in used_player_ids:
                raise ValueError(f"{player['name']} no puede aparecer más de una vez en el partido.")
            used_player_ids.add(submitted_player_id)
            ref = f"p-{submitted_player_id}"
            participants[side].append({"ref": ref, "player_id": submitted_player_id})
        else:
            ref = f"c-{side.lower()}-{idx}"
            participants[side].append({"ref": ref, "name": name})
        goals_for = _nonnegative_int(
            request.POST.get(f"participant_{side}_goals_{idx}", 0), f"Goles de {name}"
        )
        own_goals = _nonnegative_int(
            request.POST.get(f"participant_{side}_own_goals_{idx}", 0),
            f"Goles en contra de {name}",
        )
        goals.extend({"participant_ref": ref, "own_goal": False} for _ in range(goals_for))
        goals.extend({"participant_ref": ref, "own_goal": True} for _ in range(own_goals))

    minimum = form.cleaned_data["players_per_team"]
    if len(participants["A"]) < minimum:
        raise ValueError(f"Equipo A requiere al menos {minimum} participantes para F{minimum}.")
    if len(participants["B"]) < minimum:
        raise ValueError(f"Equipo B requiere al menos {minimum} participantes para F{minimum}.")

    played_at = form.cleaned_data["played_at"]
    return {
        "played_at": played_at.isoformat(),
        "players_per_team": minimum,
        "location": form.cleaned_data["location"] or None,
        "team_a": {
            "name": form.cleaned_data["team_a_name"],
            "score": form.cleaned_data["score_a"],
            "participants": participants["A"],
        },
        "team_b": {
            "name": form.cleaned_data["team_b_name"],
            "score": form.cleaned_data["score_b"],
            "participants": participants["B"],
        },
        "goals": goals,
    }

def _match_editor(request, group_id, match_id=None):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
        match = api.matches.get(group_id, match_id) if match_id else None
        all_players = api.players.list(group_id, include_inactive=True)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("matches-list", group_id=group_id)

    selected_player_ids = {str(p.get("player_id")) for p in (match or {}).get("participants", []) if p.get("player_id")}
    players = [p for p in all_players if p.get("active") or str(p["id"]) in selected_player_ids]
    initial = _initial_match_form(match) if match else None
    form = MatchForm(request.POST or None, initial=initial)
    raw_minimum = (
        request.POST.get("players_per_team")
        if request.method == "POST"
        else (initial or {}).get("players_per_team", 5)
    )
    try:
        editor_minimum = min(50, max(1, int(raw_minimum)))
    except (TypeError, ValueError):
        editor_minimum = 5
    participant_rows = _participant_editor_rows(players, request, match, editor_minimum)

    if request.method == "POST" and form.is_valid():
        try:
            payload = _build_match_payload(request, form, players)
            saved = api.matches.update(group_id, match_id, payload) if match else api.matches.create(group_id, payload)
        except ValueError as exc:
            form.add_error(None, str(exc))
        except ApiError as exc:
            form.add_error(None, _api_message(exc))
        else:
            messages.success(request, "Partido actualizado." if match else "Partido guardado.")
            return redirect("match-detail", group_id=group_id, match_id=saved["id"])

    return render(
        request,
        "fulbacho/matches/form.html",
        {
            "group": group,
            "match": match,
            "match_form": form,
            "participant_rows": participant_rows,
            "team_columns": [
                {"side": "A", "rows": participant_rows["A"]},
                {"side": "B", "rows": participant_rows["B"]},
            ],
            "autocomplete_players": [
                {
                    "id": str(player["id"]),
                    "name": player["name"],
                    "active": player.get("active", True),
                }
                for player in players
            ],
            "players_count": len([p for p in players if p.get("active")]),
            "title": "Editar partido" if match else "Nuevo partido",
            "active_tab": "matches",
        },
    )


@api_login_required
def matches_list(request, group_id):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
        matches = api.matches.list(group_id, limit=100)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("groups-index")
    return render(request, "fulbacho/matches/list.html", {"group": group, "matches": matches, "guest_mode": False, "active_tab": "matches"})


def _match_to_import_payload(match):
    participant_refs = {}
    teams = {"A": [], "B": []}
    for index, participant in enumerate(match.get("participants", [])):
        ref = f"r{index}"
        participant_refs[str(participant["id"])] = ref
        item = {"ref": ref}
        if participant.get("player_id"):
            item["player_id"] = str(participant["player_id"])
        else:
            item["name"] = participant["display_name"]
        teams[participant["team"]].append(item)
    goals = []
    for goal in match.get("goals", []):
        participant_id = goal.get("participant_id")
        if participant_id:
            goals.append({
                "participant_ref": participant_refs[str(participant_id)],
                "own_goal": bool(goal.get("own_goal")),
            })
        else:
            goals.append({
                "participant_ref": None,
                "own_goal": False,
                "team_scored_for": goal["team_scored_for"],
            })
    played_at = match["played_at"]
    if hasattr(played_at, "isoformat"):
        played_at = played_at.isoformat()
    return {
        "played_at": played_at,
        "players_per_team": match["players_per_team"],
        "location": match.get("location"),
        "team_a": {"name": match["team_a_name"], "score": match["score_a"], "participants": teams["A"]},
        "team_b": {"name": match["team_b_name"], "score": match["score_b"], "participants": teams["B"]},
        "goals": goals,
    }


@api_login_required
def matches_export_csv(request, group_id):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
        matches = _all_matches(api, group_id)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("matches-list", group_id=group_id)
    rows = []
    for match in matches:
        payload = _match_to_import_payload(match)
        rows.append(
            {
                "id": match["id"],
                "played_at": payload["played_at"],
                "players_per_team": match["players_per_team"],
                "team_a_name": match["team_a_name"],
                "team_b_name": match["team_b_name"],
                "score_a": match["score_a"],
                "score_b": match["score_b"],
                "payload_json": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            }
        )
    return _csv_response(
        f"fulbacho-{group['code']}-partidos.csv",
        ["id", "played_at", "players_per_team", "team_a_name", "team_b_name", "score_a", "score_b", "payload_json"],
        rows,
    )


@api_login_required
def matches_import_csv(request, group_id):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("groups-index")
    form = CsvImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            rows, columns = _read_csv_upload(form.cleaned_data["file"])
            if "payload_json" not in columns:
                raise ValueError("El CSV debe incluir payload_json. Usá una exportación de Fulbacho v2 como formato base.")
            imported = 0
            for row_number, row in enumerate(rows, start=2):
                raw = (row.get("payload_json") or "").strip()
                if not raw:
                    raise ValueError(f"Fila {row_number}: payload_json está vacío.")
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Fila {row_number}: payload_json no es JSON válido.") from exc
                api.matches.create(group_id, payload)
                imported += 1
        except (ValueError, ApiError) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else _api_message(exc))
        else:
            messages.success(request, f"Se importaron {imported} partidos a través de la API.")
            return redirect("matches-list", group_id=group_id)
    return render(request, "fulbacho/import_csv.html", {
        "group": group,
        "form": form,
        "title": "Importar partidos",
        "description": "Formato v2: exportá partidos desde Fulbacho y reutilizá la columna payload_json. Los IDs de jugadores habituales deben existir en el grupo destino.",
        "cancel_url": reverse("matches-list", args=[group_id]),
        "active_tab": "matches",
    })


@api_login_required
def match_create(request, group_id):
    return _match_editor(request, group_id)


@api_login_required
def match_detail(request, group_id, match_id):
    api = api_for(request)
    try:
        group = api.groups.get(group_id)
        match = api.matches.get(group_id, match_id)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("matches-list", group_id=group_id)
    return render(request, "fulbacho/matches/detail.html", {"group": group, "match": match, "team_summaries": _team_summaries(match), "guest_mode": False, "active_tab": "matches"})


@api_login_required
def match_edit(request, group_id, match_id):
    try:
        match = api_for(request).matches.get(group_id, match_id)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("matches-list", group_id=group_id)
    if not match.get("can_edit"):
        messages.error(request, "Este partido ya no se puede editar: pasaron más de 24 horas desde su carga.")
        return redirect("match-detail", group_id=group_id, match_id=match_id)
    return _match_editor(request, group_id, match_id)


def guest_code(request):
    form = GuestCodeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        code = form.cleaned_data["code"]
        try:
            api_for(request).guest.group(code)
        except ApiError as exc:
            form.add_error("code", _api_message(exc))
        else:
            return redirect("guest-dashboard", code=code)
    return render(request, "fulbacho/guest/code_form.html", {"form": form, "guest_mode": True})


def guest_dashboard(request, code):
    api = api_for(request)
    try:
        group = api.guest.group(code)
        dashboard = _dashboard(api, code=code)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("guest-code")
    return render(request, "fulbacho/dashboard.html", {"group": group, "dashboard": dashboard, "guest_mode": True, "active_tab": "dashboard"})


def guest_players(request, code):
    api = api_for(request)
    try:
        group = api.guest.group(code)
        players = api.guest.players(code)
        stats = api.guest.player_stats_list(code)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("guest-code")
    stats_by_id = {str(item["player_id"]): item for item in stats}
    player_stats = [stats_by_id.get(str(player["id"]), {"player_id": player["id"], "name": player["name"]}) for player in players]
    return render(request, "fulbacho/players/list.html", {"group": group, "players": players, "player_stats": player_stats, "guest_mode": True, "active_tab": "players"})


def guest_player_detail(request, code, player_id):
    api = api_for(request)
    try:
        group = api.guest.group(code)
        player = api.guest.player(code, player_id)
        stats = api.guest.player_stats(code, player_id)
        matches = api.guest.matches(code, player_id=player_id, limit=20)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("guest-players", code=code)
    return render(request, "fulbacho/players/detail.html", {"group": group, "player": player, "stats": stats, "appearances": _appearance_rows(matches, str(player_id)), "guest_mode": True, "active_tab": "players"})


def guest_matches(request, code):
    api = api_for(request)
    try:
        group = api.guest.group(code)
        matches = api.guest.matches(code, limit=100)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("guest-code")
    return render(request, "fulbacho/matches/list.html", {"group": group, "matches": matches, "guest_mode": True, "active_tab": "matches"})


def guest_match_detail(request, code, match_id):
    api = api_for(request)
    try:
        group = api.guest.group(code)
        match = api.guest.match(code, match_id)
    except ApiError as exc:
        messages.error(request, _api_message(exc))
        return redirect("guest-matches", code=code)
    return render(request, "fulbacho/matches/detail.html", {"group": group, "match": match, "team_summaries": _team_summaries(match), "guest_mode": True, "active_tab": "matches"})
