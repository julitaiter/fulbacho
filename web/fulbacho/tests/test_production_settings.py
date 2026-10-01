"""Settings must never direct Django sessions to the domain database."""
import json
import os
import subprocess
import sys

from django.test import SimpleTestCase


class ProductionSettingsTests(SimpleTestCase):
    def settings_process(self, **overrides):
        env = {key: value for key, value in os.environ.items() if key in ("PATH", "HOME")}
        env.update(
            ENVIRONMENT="production",
            API_SECRET_KEY="independent-api-test-secret",
            API_DEBUG="false",
            DJANGO_SECRET_KEY="independent-web-test-secret",
            DJANGO_DEBUG="false",
            DATABASE_URL="postgresql+psycopg://user:password@db/fulbacho",
            WEB_DATABASE_URL="postgresql://user:password@db/fulbacho_web",
            ALLOWED_HOSTS="example.test",
            CSRF_TRUSTED_ORIGINS="https://example.test",
            API_BASE_URL="http://127.0.0.1:8001/api/v1",
        )
        env.update(overrides)
        return subprocess.run(
            [sys.executable, "-c", (
                "import json; from config import settings as s; "
                "print(json.dumps({'database': s.DATABASES['default']['NAME'], "
                "'secret': s.SECRET_KEY, 'debug': s.DEBUG}))"
            )],
            env=env, capture_output=True, text=True,
        )

    def test_web_database_wins_over_domain_database(self):
        result = self.settings_process()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["database"], "fulbacho_web")

    def test_production_rejects_domain_database_even_with_encoded_name(self):
        for url in (
            "postgresql://other:password@db/fulbacho?sslmode=require",
            "postgresql://other:password@db/%66ulbacho",
        ):
            with self.subTest(url=url):
                self.assertNotEqual(self.settings_process(WEB_DATABASE_URL=url).returncode, 0)

    def test_production_requires_postgres_web_database(self):
        for url in ("", "sqlite:////tmp/sessions.sqlite3"):
            with self.subTest(url=url):
                self.assertNotEqual(self.settings_process(WEB_DATABASE_URL=url).returncode, 0)

    def test_production_requires_distinct_explicit_secrets(self):
        for secret in ("", "independent-api-test-secret"):
            with self.subTest(secret=secret):
                self.assertNotEqual(self.settings_process(DJANGO_SECRET_KEY=secret).returncode, 0)

    def test_production_rejects_debug_and_legacy_only_debug(self):
        for debug in ("true", ""):
            with self.subTest(debug=debug):
                self.assertNotEqual(self.settings_process(DJANGO_DEBUG=debug, DEBUG="false").returncode, 0)

    def test_production_requires_explicit_hosts_and_https_origins(self):
        for values in (
            {"ALLOWED_HOSTS": ""}, {"ALLOWED_HOSTS": "*"},
            {"ALLOWED_HOSTS": ".onrender.com"}, {"CSRF_TRUSTED_ORIGINS": ""},
            {"CSRF_TRUSTED_ORIGINS": "https://*.example.test"},
            {"CSRF_TRUSTED_ORIGINS": "http://example.test"},
        ):
            with self.subTest(values=values):
                self.assertNotEqual(self.settings_process(**values).returncode, 0)

    def test_production_rejects_public_api_url(self):
        self.assertNotEqual(self.settings_process(API_BASE_URL="https://example.test/api/v1").returncode, 0)

    def test_namespaced_settings_win_over_legacy_settings(self):
        result = self.settings_process(SECRET_KEY="legacy-secret", DEBUG="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["secret"], "independent-web-test-secret")
        self.assertFalse(json.loads(result.stdout)["debug"])

    def test_health_is_public_and_does_not_query_api(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
