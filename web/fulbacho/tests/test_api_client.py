from unittest.mock import call, patch

import httpx
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings

from fulbacho.api_client.client import ApiClient
from fulbacho.auth import AnonymousApiUser


USER = {
    "id": "c909c4f4-08f4-4c3f-96a8-2c671252df85",
    "email": "ana@example.com",
    "display_name": "Ana",
    "is_active": True,
}


def api_response(status_code, payload=None):
    request = httpx.Request("POST", "http://api.test/api/v1/auth/test")
    if payload is None:
        return httpx.Response(status_code, request=request)
    return httpx.Response(status_code, json=payload, request=request)


def request_with_session(path="/"):
    request = RequestFactory().get(path)
    SessionMiddleware(lambda django_request: None).process_request(request)
    request.session.save()
    request.user = AnonymousApiUser()
    return request


@override_settings(
    API_BASE_URL="http://api.test/api/v1",
    API_TIMEOUT_SECONDS=1,
    SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies",
)
class ApiClientTests(SimpleTestCase):
    def test_post_with_wsgi_request_calls_httpx_not_django_request(self):
        django_request = request_with_session()
        client = ApiClient(django_request)

        with patch("fulbacho.api_client.client.httpx.request", return_value=api_response(200, {"ok": True})) as send:
            result = client.post("/auth/register", json={"email": "ana@example.com"}, auth=False)

        self.assertEqual(result, {"ok": True})
        self.assertIs(client.django_request, django_request)
        self.assertNotIn("request", client.__dict__)
        send.assert_called_once_with(
            "POST",
            "http://api.test/api/v1/auth/register",
            headers={},
            timeout=1,
            json={"email": "ana@example.com"},
        )

    def test_refresh_retries_with_new_access_token_and_updates_session(self):
        django_request = request_with_session()
        django_request.session.update(
            {"access_token": "old-access", "refresh_token": "old-refresh", "api_user": USER}
        )
        refreshed = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "user": USER,
        }

        with (
            patch(
                "fulbacho.api_client.client.httpx.request",
                side_effect=[api_response(401, {"detail": "expired"}), api_response(200, {"groups": []})],
            ) as send,
            patch("fulbacho.api_client.client.httpx.post", return_value=api_response(200, refreshed)) as refresh,
        ):
            result = ApiClient(django_request).get("/groups")

        self.assertEqual(result, {"groups": []})
        self.assertEqual(django_request.session["access_token"], "new-access")
        self.assertEqual(django_request.session["refresh_token"], "new-refresh")
        self.assertEqual(django_request.user.email, USER["email"])
        refresh.assert_called_once_with(
            "http://api.test/api/v1/auth/refresh",
            json={"refresh_token": "old-refresh"},
            timeout=1,
        )
        self.assertEqual(
            send.call_args_list,
            [
                call(
                    "GET",
                    "http://api.test/api/v1/groups",
                    headers={"Authorization": "Bearer old-access"},
                    timeout=1,
                    params=None,
                ),
                call(
                    "GET",
                    "http://api.test/api/v1/groups",
                    headers={"Authorization": "Bearer new-access"},
                    timeout=1,
                    params=None,
                ),
            ],
        )

    def test_store_and_clear_auth_keep_session_and_user_in_sync(self):
        django_request = request_with_session()
        client = ApiClient(django_request)
        payload = {
            "access_token": "access",
            "refresh_token": "refresh",
            "user": USER,
        }

        client.store_auth(payload)

        self.assertEqual(django_request.session["access_token"], "access")
        self.assertEqual(django_request.session["refresh_token"], "refresh")
        self.assertEqual(django_request.session["api_user"], USER)
        self.assertTrue(django_request.session.modified)
        self.assertEqual(django_request.user.email, USER["email"])

        client.clear_auth()

        self.assertNotIn("access_token", django_request.session)
        self.assertNotIn("refresh_token", django_request.session)
        self.assertNotIn("api_user", django_request.session)
        self.assertFalse(django_request.user.is_authenticated)


@override_settings(
    API_BASE_URL="http://api.test/api/v1",
    API_TIMEOUT_SECONDS=1,
)
class AuthViewTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_successful_registration_stores_auth_and_redirects(self):
        payload = {
            "access_token": "access",
            "refresh_token": "refresh",
            "user": USER,
        }

        with patch("fulbacho.api_client.client.httpx.request", return_value=api_response(201, payload)) as send:
            response = self.client.post(
                "/registro/",
                {
                    "display_name": "Ana",
                    "email": "ana@example.com",
                    "password": "password-123",
                    "password_confirm": "password-123",
                },
            )

        self.assertRedirects(response, "/grupos/", fetch_redirect_response=False)
        self.assertEqual(self.client.session["access_token"], "access")
        self.assertEqual(self.client.session["refresh_token"], "refresh")
        self.assertEqual(self.client.session["api_user"], USER)
        self.assertEqual(send.call_args.kwargs["json"], {
            "email": "ana@example.com",
            "password": "password-123",
            "display_name": "Ana",
        })
        self.assertEqual(send.call_args.kwargs["headers"], {})

    def test_successful_login_stores_auth_and_redirects(self):
        payload = {
            "access_token": "access",
            "refresh_token": "refresh",
            "user": USER,
        }

        with patch("fulbacho.api_client.client.httpx.request", return_value=api_response(200, payload)) as send:
            response = self.client.post(
                "/accounts/login/",
                {"email": "ana@example.com", "password": "password-123"},
            )

        self.assertRedirects(response, "/grupos/", fetch_redirect_response=False)
        self.assertEqual(self.client.session["api_user"], USER)
        self.assertEqual(send.call_args.kwargs["json"], {
            "email": "ana@example.com",
            "password": "password-123",
        })

    def test_logout_revokes_refresh_token_and_flushes_session(self):
        session = self.client.session
        session.update(
            {"access_token": "access", "refresh_token": "refresh", "api_user": USER}
        )
        session.save()

        with patch("fulbacho.api_client.client.httpx.request", return_value=api_response(204)) as send:
            response = self.client.post("/accounts/logout/")

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertNotIn("access_token", self.client.session)
        self.assertNotIn("refresh_token", self.client.session)
        self.assertNotIn("api_user", self.client.session)
        self.assertEqual(send.call_args.kwargs["json"], {"refresh_token": "refresh"})
        self.assertEqual(send.call_args.kwargs["headers"], {})

    def test_authenticated_groups_access_sends_bearer_token(self):
        session = self.client.session
        session.update(
            {"access_token": "access", "refresh_token": "refresh", "api_user": USER}
        )
        session.save()

        with patch("fulbacho.api_client.client.httpx.request", return_value=api_response(200, [])) as send:
            response = self.client.get("/grupos/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Todavía no tenés grupos")
        self.assertContains(response, 'action="/accounts/logout/"')
        self.assertContains(response, USER["display_name"])
        self.assertEqual(send.call_args.kwargs["headers"], {"Authorization": "Bearer access"})
