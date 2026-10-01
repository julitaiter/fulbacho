from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .api_client import ApiError, api_for
from .auth import user_from_session


def admin_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/accounts/login/?{urlencode({'next': request.get_full_path()})}")
        api = api_for(request)
        try:
            # Session flags are display hints; permissions are fetched on every admin request.
            current_user = api.auth.me()
            request.session["api_user"] = current_user
            request.user = user_from_session(request.session)
            if not request.user.is_active or not request.user.is_superuser:
                return HttpResponseForbidden("Se requiere superusuario global.")
            return view(request, api, *args, **kwargs)
        except ApiError as error:
            if error.status_code == 401:
                request.session.flush()
                return redirect(f"/accounts/login/?{urlencode({'next': request.get_full_path()})}")
            return render(
                request, "fulbacho/admin/error.html", {"detail": error.detail},
                status=error.status_code,
            )
    return wrapped


@admin_required
def dashboard(request, api):
    return render(request, "fulbacho/admin/dashboard.html")


def _list(request, api, resource, title):
    try:
        offset = int(request.GET.get("offset", "0"))
        if offset < 0:
            raise ValueError
    except ValueError:
        return HttpResponseBadRequest("Offset inválido.")
    items = getattr(api.admin, resource)(offset=offset, limit=50)
    return render(request, f"fulbacho/admin/{resource}.html", {
        resource: items, "title": title,
        "previous_offset": max(0, offset - 50) if offset else None,
        "next_offset": offset + 50 if len(items) == 50 else None,
    })


@admin_required
def users(request, api):
    return _list(request, api, "users", "Usuarios")


@admin_required
def user_detail(request, api, user_id):
    return render(request, "fulbacho/admin/user_detail.html", {"admin_user": api.admin.user(user_id)})


def _update_user(request, api, user_id, field):
    value = request.POST.get("value")
    if value not in ("true", "false"):
        return HttpResponseBadRequest("Valor inválido.")
    user = api.admin.update_user(user_id, **{field: value == "true"})
    messages.success(request, "Usuario actualizado.")
    if str(user_id) == request.user.id:
        request.session["api_user"] = user
        request.user = user_from_session(request.session)
        if not request.user.is_active:
            request.session.flush()
            return redirect("login")
        if not request.user.is_superuser:
            return redirect("groups-index")
    return redirect("admin-user-detail", user_id=user_id)


@require_POST
@admin_required
def user_active(request, api, user_id):
    return _update_user(request, api, user_id, "is_active")


@require_POST
@admin_required
def user_superuser(request, api, user_id):
    return _update_user(request, api, user_id, "is_superuser")


@admin_required
def groups(request, api):
    return _list(request, api, "groups", "Grupos")


@admin_required
def group_detail(request, api, group_id):
    return render(request, "fulbacho/admin/group_detail.html", {
        "admin_group": api.admin.group(group_id), "members": api.admin.members(group_id),
    })


@admin_required
def matches(request, api):
    return _list(request, api, "matches", "Partidos")


@admin_required
def match_detail(request, api, match_id):
    return render(request, "fulbacho/admin/match_detail.html", {"match": api.admin.match(match_id)})
