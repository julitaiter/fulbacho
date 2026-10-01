import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_namespaced_values_override_legacy_values(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("API_SECRET_KEY", "api-specific-secret")
    monkeypatch.setenv("SECRET_KEY", "legacy-secret")
    monkeypatch.setenv("API_DEBUG", "false")
    monkeypatch.setenv("DEBUG", "true")
    settings = Settings(_env_file=None)
    assert settings.secret_key == "api-specific-secret"
    assert settings.debug is False


def test_legacy_local_environment_is_supported(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("API_SECRET_KEY", raising=False)
    monkeypatch.delenv("API_DEBUG", raising=False)
    monkeypatch.setenv("SECRET_KEY", "legacy-api-secret")
    monkeypatch.setenv("DEBUG", "true")
    settings = Settings(_env_file=None)
    assert settings.secret_key == "legacy-api-secret"
    assert settings.debug is True


def test_production_rejects_legacy_only_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("API_SECRET_KEY", raising=False)
    monkeypatch.setenv("SECRET_KEY", "legacy-api-secret")
    monkeypatch.setenv("API_DEBUG", "false")
    with pytest.raises(ValidationError, match="API_SECRET_KEY") as error:
        Settings(_env_file=None)
    assert "legacy-api-secret" not in str(error.value)


def test_production_rejects_debug_and_shared_secrets(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("API_SECRET_KEY", "independent-api-secret")
    monkeypatch.setenv("DJANGO_SECRET_KEY", "independent-django-secret")
    monkeypatch.setenv("API_DEBUG", "true")
    with pytest.raises(ValidationError, match="API_DEBUG=false"):
        Settings(_env_file=None)
    monkeypatch.setenv("API_DEBUG", "false")
    monkeypatch.setenv("DJANGO_SECRET_KEY", "independent-api-secret")
    with pytest.raises(ValidationError, match="distinct"):
        Settings(_env_file=None)
