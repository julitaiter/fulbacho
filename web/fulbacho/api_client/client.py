from __future__ import annotations

from typing import Any

import httpx
from django.conf import settings
from django.utils.dateparse import parse_datetime

from .exceptions import ApiError, ApiUnavailable


_DATETIME_KEYS = {"created_at", "updated_at", "played_at", "joined_at", "match_played_at", "expires_at"}


def _coerce_datetimes(value):
    if isinstance(value, list):
        return [_coerce_datetimes(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in _DATETIME_KEYS and isinstance(item, str):
                result[key] = parse_datetime(item) or item
            else:
                result[key] = _coerce_datetimes(item)
        return result
    return value


class ApiClient:
    def __init__(self, django_request=None):
        self.django_request = django_request
        self.base_url = settings.API_BASE_URL
        self.timeout = settings.API_TIMEOUT_SECONDS

    @property
    def access_token(self) -> str | None:
        if not self.django_request:
            return None
        return self.django_request.session.get("access_token")

    @property
    def refresh_token(self) -> str | None:
        if not self.django_request:
            return None
        return self.django_request.session.get("refresh_token")

    def _normalize_error(self, response: httpx.Response) -> ApiError:
        try:
            payload = response.json()
        except ValueError:
            return ApiError(
                f"La API respondió con HTTP {response.status_code}.",
                status_code=response.status_code,
            )

        detail = payload.get("detail", "Error de API") if isinstance(payload, dict) else payload
        if isinstance(detail, list):
            parts = []
            for item in detail:
                if not isinstance(item, dict):
                    parts.append(str(item))
                    continue
                loc = ".".join(str(piece) for piece in item.get("loc", []) if piece != "body")
                msg = item.get("msg", "Dato inválido")
                parts.append(f"{loc}: {msg}" if loc else msg)
            detail = "; ".join(parts)
        elif not isinstance(detail, str):
            detail = str(detail)

        code = payload.get("code") if isinstance(payload, dict) else None
        return ApiError(detail, status_code=response.status_code, code=code)

    def _refresh(self) -> bool:
        if not self.django_request or not self.refresh_token:
            return False

        try:
            response = httpx.post(
                f"{self.base_url}/auth/refresh",
                json={"refresh_token": self.refresh_token},
                timeout=self.timeout,
            )
        except httpx.HTTPError:
            return False

        if response.status_code >= 400:
            return False

        payload = response.json()
        self.store_auth(payload)
        return True

    def store_auth(self, payload: dict[str, Any]) -> None:
        if not self.django_request:
            return

        self.django_request.session["access_token"] = payload["access_token"]
        self.django_request.session["refresh_token"] = payload["refresh_token"]
        self.django_request.session["api_user"] = payload["user"]
        self.django_request.session.modified = True

        from fulbacho.auth import user_from_session

        self.django_request.user = user_from_session(
            self.django_request.session
        )

    def clear_auth(self) -> None:
        if not self.django_request:
            return

        for key in (
            "access_token",
            "refresh_token",
            "api_user",
        ):
            self.django_request.session.pop(key, None)

        self.django_request.session.modified = True

        from fulbacho.auth import AnonymousApiUser

        self.django_request.user = AnonymousApiUser()

    def _request(
        self,
        method: str,
        path: str,
        *,
        auth: bool = True,
        retry_auth: bool = True,
        **kwargs,
    ):
        headers = dict(kwargs.pop("headers", {}))
        if auth:
            token = self.access_token
            if not token:
                raise ApiError("La sesión venció. Iniciá sesión nuevamente.", status_code=401)
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=self.timeout,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise ApiUnavailable() from exc

        if response.status_code == 401 and auth and retry_auth and self._refresh():
            return self._request(method, path, auth=True, retry_auth=False, **kwargs)

        if response.status_code >= 400:
            if response.status_code == 401 and auth:
                self.clear_auth()
            raise self._normalize_error(response)

        if response.status_code == 204 or not response.content:
            return None
        return _coerce_datetimes(response.json())

    def get(self, path: str, *, params=None, auth: bool = True):
        return self._request("GET", path, params=params, auth=auth)

    def post(self, path: str, *, json=None, auth: bool = True):
        return self._request("POST", path, json=json, auth=auth)

    def patch(self, path: str, *, json=None, auth: bool = True):
        return self._request("PATCH", path, json=json, auth=auth)

    def patch(self, path: str, *, json=None, auth: bool = True):
        return self._request("PATCH", path, json=json, auth=auth)

    def put(self, path: str, *, json=None, auth: bool = True):
        return self._request("PUT", path, json=json, auth=auth)

    def delete(self, path: str, *, auth: bool = True):
        return self._request("DELETE", path, auth=auth)
