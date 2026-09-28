from dataclasses import dataclass
from functools import wraps
from urllib.parse import urlencode

from django.shortcuts import redirect


@dataclass(frozen=True)
class ApiUser:
    id: str
    email: str
    display_name: str
    is_active: bool = True

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def __str__(self) -> str:
        return self.display_name or self.email


class AnonymousApiUser:
    id = None
    email = ""
    display_name = ""
    is_active = False
    is_authenticated = False
    is_anonymous = True

    def __bool__(self):
        return False

    def __str__(self):
        return "AnonymousUser"


def user_from_session(session):
    payload = session.get("api_user")
    if not payload:
        return AnonymousApiUser()
    try:
        return ApiUser(
            id=str(payload["id"]),
            email=payload["email"],
            display_name=payload["display_name"],
            is_active=payload.get("is_active", True),
        )
    except (KeyError, TypeError):
        return AnonymousApiUser()


class ApiAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user = user_from_session(request.session)
        return self.get_response(request)


def api_login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            query = urlencode({"next": request.get_full_path()})
            return redirect(f"/accounts/login/?{query}")
        return view_func(request, *args, **kwargs)

    return wrapped
