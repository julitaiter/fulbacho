from unittest.mock import patch

import httpx
from django.conf import settings
from django.test import Client, SimpleTestCase, override_settings


USER_ID = "ad88cfe4-a5a7-4ef1-a3e9-3e41e69d84ee"
TARGET_ID = "36aee633-32f0-49eb-a15b-b5a1ce6946c5"
GROUP_ID = "30405221-ae73-4983-8b4d-681e687523a7"
MATCH_ID = "b9745e0c-84df-4ffb-b583-459c52d67c59"


@override_settings(
    SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies",
    API_BASE_URL="http://api.test/api/v1", API_TIMEOUT_SECONDS=1,
)
class AdminViewsTests(SimpleTestCase):
    # SimpleTestCase forbids all Django DB access: every domain operation below is HTTP.
    def setUp(self):
        self.user = {"id": USER_ID, "email": "root@example.com", "display_name": "Root", "is_active": True, "is_superuser": True}
        self.target = {**self.user, "id": TARGET_ID, "is_superuser": False}
        self.group = {"id": GROUP_ID, "name": "Private group", "code": "ABC123", "created_at": "2026-10-01T12:00:00Z"}
        self.match = {
            "id": MATCH_ID, "group_id": GROUP_ID, "team_a_name": "A", "team_b_name": "B",
            "score_a": 1, "score_b": 0, "played_at": "2026-10-01T12:00:00Z",
            "players_per_team": 5, "location": None,
            "participants": [{"id": TARGET_ID, "display_name": "Ana", "team": "A"}],
            "goals": [{"team_scored_for": "A", "participant_id": None, "own_goal": False}],
        }
        self.send = self.enterContext(patch("fulbacho.api_client.client.httpx.request", side_effect=self.response))

    def response(self, method, url, **kwargs):
        path = url.removeprefix("http://api.test/api/v1")
        payloads = {
            "/auth/me": self.user,
            "/groups/overview": [],
            "/admin/users": [self.target],
            f"/admin/users/{TARGET_ID}": self.target,
            f"/admin/users/{USER_ID}": self.user,
            "/admin/groups": [self.group],
            f"/admin/groups/{GROUP_ID}": self.group,
            f"/admin/groups/{GROUP_ID}/members": [{"user_id": TARGET_ID, "display_name": "Ana", "email": "ana@example.com", "role": "admin"}],
            "/admin/matches": [self.match],
            f"/admin/matches/{MATCH_ID}": self.match,
        }
        self.assertIn(path, payloads)
        result = payloads[path]
        if method == "PATCH":
            result = {**result, **kwargs["json"]}
        return httpx.Response(200, json=result, request=httpx.Request(method, url))

    def login(self, **flags):
        session = self.client.session
        session.update({"access_token": "access", "refresh_token": "refresh", "api_user": {**self.user, **flags}})
        session.save()
        self.client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

    def test_anonymous_is_redirected_without_api_request(self):
        response = self.client.get("/admin/")
        self.assertRedirects(response, "/accounts/login/?next=%2Fadmin%2F", fetch_redirect_response=False)
        self.send.assert_not_called()

    def test_normal_user_cannot_access_or_mutate_admin(self):
        self.user["is_superuser"] = False
        self.login()
        self.assertEqual(self.client.get("/admin/").status_code, 403)
        self.assertEqual(self.client.post(f"/admin/users/{TARGET_ID}/superuser/", {"value": "true"}).status_code, 403)
        self.assertTrue(all(call.args[1].endswith("/auth/me") for call in self.send.call_args_list))

    def test_stale_superuser_session_does_not_grant_access(self):
        self.login(is_superuser=True)
        self.user["is_superuser"] = False
        self.assertEqual(self.client.get("/admin/").status_code, 403)
        self.assertFalse(self.client.session["api_user"]["is_superuser"])

    def test_promoted_user_with_stale_normal_session_can_access(self):
        self.login(is_superuser=False)
        self.assertContains(self.client.get("/admin/"), "Administración global")
        self.assertTrue(self.client.session["api_user"]["is_superuser"])

    def test_all_admin_pages_render_using_only_http(self):
        self.login()
        for path in (
            "/admin/", "/admin/users/", f"/admin/users/{TARGET_ID}/",
            "/admin/groups/", f"/admin/groups/{GROUP_ID}/",
            "/admin/matches/", f"/admin/matches/{MATCH_ID}/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertTrue(any(call.args[1].endswith(f"/admin/groups/{GROUP_ID}/members") for call in self.send.call_args_list))

    def test_navigation_only_shows_administration_to_superuser(self):
        self.login(is_superuser=False)
        self.assertNotContains(self.client.get("/grupos/"), 'href="/admin/"')
        self.login(is_superuser=True)
        self.assertContains(self.client.get("/grupos/"), 'href="/admin/"')

    def test_admin_actions_patch_api_without_any_database_access(self):
        self.login()
        for action, field in (("active", "is_active"), ("superuser", "is_superuser")):
            for value in ("true", "false"):
                with self.subTest(action=action, value=value):
                    response = self.client.post(f"/admin/users/{TARGET_ID}/{action}/", {"value": value})
                    self.assertEqual(response.status_code, 302)
                    self.send.assert_called_with(
                        "PATCH", f"http://api.test/api/v1/admin/users/{TARGET_ID}",
                        headers={"Authorization": "Bearer access"}, timeout=1,
                        json={field: value == "true"},
                    )

    def test_mutations_require_post_and_valid_boolean(self):
        self.login()
        path = f"/admin/users/{TARGET_ID}/active/"
        self.assertEqual(self.client.get(path).status_code, 405)
        self.assertEqual(self.client.post(path, {"value": "anything"}).status_code, 400)
        self.assertFalse(any(call.args[0] == "PATCH" for call in self.send.call_args_list))

    def test_mutations_are_csrf_protected(self):
        self.login()
        client = Client(enforce_csrf_checks=True)
        client.cookies = self.client.cookies.copy()
        self.assertEqual(client.post(f"/admin/users/{TARGET_ID}/active/", {"value": "false"}).status_code, 403)
        self.send.assert_not_called()

    def test_api_denial_is_preserved(self):
        self.login()
        def deny(method, url, **kwargs):
            if url.endswith("/auth/me"):
                return self.response(method, url, **kwargs)
            return httpx.Response(403, json={"detail": "Permission revoked"}, request=httpx.Request(method, url))
        self.send.side_effect = deny
        self.assertContains(self.client.get("/admin/users/"), "Permission revoked", status_code=403)

    def test_inactive_or_expired_session_cannot_access(self):
        self.login()
        self.user["is_active"] = False
        self.assertEqual(self.client.get("/admin/").status_code, 403)
        self.send.side_effect = lambda method, url, **kw: httpx.Response(
            401, json={"detail": "Unavailable"}, request=httpx.Request(method, url)
        )
        with patch("fulbacho.api_client.client.httpx.post", return_value=httpx.Response(401)):
            self.assertEqual(self.client.get("/admin/").status_code, 302)
        self.assertNotIn("access_token", self.client.session)

    def test_self_demotion_updates_session_and_redirects_out_of_admin(self):
        self.login()
        response = self.client.post(f"/admin/users/{USER_ID}/superuser/", {"value": "false"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/grupos/")
        self.assertFalse(self.client.session["api_user"]["is_superuser"])
