from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.security import hash_password, verify_password
from app.modules.auth.bootstrap import bootstrap_superuser
from app.modules.auth.models import User


def bootstrap_env():
    return {
        "BOOTSTRAP_SUPERUSER_EMAIL": f"{uuid4()}@example.com",
        "BOOTSTRAP_SUPERUSER_PASSWORD": "bootstrap-test-password",
        "BOOTSTRAP_SUPERUSER_NAME": "Global admin",
    }


def test_bootstrap_creates_active_superuser_and_is_idempotent(db, capsys):
    env = bootstrap_env()
    assert bootstrap_superuser(db, env) == "created"
    user = db.scalar(select(User).where(User.email == env["BOOTSTRAP_SUPERUSER_EMAIL"]))
    assert user.is_active and user.is_superuser
    assert verify_password(env["BOOTSTRAP_SUPERUSER_PASSWORD"], user.password_hash)
    original_id, original_hash, original_updated = user.id, user.password_hash, user.updated_at
    env["BOOTSTRAP_SUPERUSER_PASSWORD"] = "another-bootstrap-password"
    assert bootstrap_superuser(db, env) == "unchanged"
    assert user.id == original_id and user.password_hash == original_hash
    assert user.updated_at == original_updated
    count = db.scalar(select(func.count()).select_from(User).where(User.email == user.email))
    assert count == 1
    assert "bootstrap-test-password" not in capsys.readouterr().out


def test_bootstrap_promotes_without_resetting_credentials_or_reactivating(db):
    env = bootstrap_env()
    user = User(email=env["BOOTSTRAP_SUPERUSER_EMAIL"], password_hash=hash_password("existing-password"), display_name="Existing", is_active=False)
    db.add(user)
    db.flush()
    original_hash = user.password_hash
    env["BOOTSTRAP_SUPERUSER_EMAIL"] = "  " + user.email.upper() + "  "
    assert bootstrap_superuser(db, env) == "promoted"
    assert user.is_superuser and not user.is_active
    assert user.password_hash == original_hash and user.display_name == "Existing"


def test_incomplete_bootstrap_does_not_touch_database(db):
    from unittest.mock import Mock

    for key in bootstrap_env():
        env = bootstrap_env()
        del env[key]
        database = Mock()
        assert bootstrap_superuser(database, env) == "skipped"
        assert database.mock_calls == []


def test_invalid_bootstrap_does_not_expose_password(db):
    env = bootstrap_env()
    env["BOOTSTRAP_SUPERUSER_PASSWORD"] = "short"
    with pytest.raises(ValueError) as error:
        bootstrap_superuser(db, env)
    assert "short" not in str(error.value)


def test_cli_bootstrap_logs_outcome_without_password(db, monkeypatch, capsys):
    import runpy
    from unittest.mock import MagicMock, patch

    env = bootstrap_env()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    context = MagicMock()
    context.__enter__.return_value = db
    script = runpy.run_path("scripts/bootstrap_superuser.py")
    with patch("app.core.database.SessionLocal", return_value=context):
        script["main"]()
    output = capsys.readouterr().out
    assert "created" in output
    assert env["BOOTSTRAP_SUPERUSER_PASSWORD"] not in output


def test_cli_missing_variables_does_not_open_database(monkeypatch, capsys):
    import runpy
    from unittest.mock import patch

    for key in bootstrap_env():
        monkeypatch.delenv(key, raising=False)
    script = runpy.run_path("scripts/bootstrap_superuser.py")
    with patch("app.core.database.SessionLocal") as sessions:
        script["main"]()
    sessions.assert_not_called()
    assert "skipped" in capsys.readouterr().out
