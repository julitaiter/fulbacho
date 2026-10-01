from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.security import create_access_token, hash_password
from app.modules.auth.models import User
from app.modules.groups.models import Group, GroupMember, GroupRole
from app.modules.matches.models import Match


@pytest.fixture
def accounts(db):
    normal = User(email=f"{uuid4()}@example.com", display_name="Group admin", password_hash=hash_password("test-password"))
    root = User(email=f"{uuid4()}@example.com", display_name="Global admin", password_hash=hash_password("test-password"), is_superuser=True)
    db.add_all([normal, root])
    db.flush()
    group = Group(name="Private group", code=str(uuid4())[:6].upper(), created_by_id=normal.id)
    db.add(group)
    db.flush()
    db.add(GroupMember(group_id=group.id, user_id=normal.id, role=GroupRole.ADMIN))
    match = Match(group_id=group.id, created_by_id=normal.id, played_at=datetime.now(UTC), players_per_team=5)
    db.add(match)
    db.flush()
    return normal, root, group, match


def headers(user):
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def admin_paths(accounts):
    normal, _, group, match = accounts
    return [
        "/admin/users", f"/admin/users/{normal.id}", "/admin/groups",
        f"/admin/groups/{group.id}", f"/admin/groups/{group.id}/members",
        "/admin/matches", f"/admin/matches/{match.id}",
    ]


def test_every_admin_endpoint_requires_global_permission(client, accounts):
    normal, _, _, _ = accounts
    for path in admin_paths(accounts):
        assert client.get(f"/api/v1{path}").status_code == 401
        assert client.get(f"/api/v1{path}", headers=headers(normal)).status_code == 403
    assert client.patch(f"/api/v1/admin/users/{normal.id}", json={"is_superuser": True}).status_code == 401
    assert client.patch(f"/api/v1/admin/users/{normal.id}", headers=headers(normal), json={"is_superuser": True}).status_code == 403


def test_global_superuser_can_inspect_groups_without_membership(client, accounts):
    normal, root, group, _ = accounts
    for path in admin_paths(accounts):
        response = client.get(f"/api/v1{path}", headers=headers(root))
        assert response.status_code == 200, response.text
        assert "password_hash" not in response.text
    members = client.get(f"/api/v1/admin/groups/{group.id}/members", headers=headers(root)).json()
    assert members[0]["user_id"] == str(normal.id)
    # Global permission never grants membership/roles in the ordinary group API.
    assert client.get(f"/api/v1/groups/{group.id}", headers=headers(root)).status_code == 403


def test_admin_can_toggle_user_flags_and_revocation_is_immediate(client, accounts):
    normal, root, _, _ = accounts
    token = headers(normal)
    path = f"/api/v1/admin/users/{normal.id}"
    promoted = client.patch(path, headers=headers(root), json={"is_superuser": True})
    assert promoted.status_code == 200
    assert promoted.json()["is_superuser"] is True
    assert client.get("/api/v1/admin/users", headers=token).status_code == 200
    me = client.get("/api/v1/auth/me", headers=token)
    assert me.json()["is_active"] is True and me.json()["is_superuser"] is True
    assert client.patch(path, headers=headers(root), json={"is_superuser": False}).status_code == 200
    assert client.get("/api/v1/admin/users", headers=token).status_code == 403
    assert client.patch(path, headers=headers(root), json={"is_active": False}).status_code == 200
    assert client.get("/api/v1/auth/me", headers=token).status_code == 401
    assert client.patch(path, headers=headers(root), json={"is_active": True}).status_code == 200
    assert client.get("/api/v1/auth/me", headers=token).status_code == 200


def test_inactive_superuser_cannot_use_admin_or_login(client, db, accounts):
    _, root, _, _ = accounts
    root.is_active = False
    db.flush()
    assert client.get("/api/v1/admin/users", headers=headers(root)).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": root.email, "password": "test-password"}).status_code == 401


def test_admin_pagination_missing_resources_and_strict_updates(client, accounts):
    normal, root, _, _ = accounts
    auth = headers(root)
    for kind in ("users", "groups", "matches"):
        assert client.get(f"/api/v1/admin/{kind}?limit=1", headers=auth).status_code == 200
        assert len(client.get(f"/api/v1/admin/{kind}?limit=1", headers=auth).json()) <= 1
        assert client.get(f"/api/v1/admin/{kind}?limit=101", headers=auth).status_code == 422
        assert client.get(f"/api/v1/admin/{kind}?offset=-1", headers=auth).status_code == 422
        assert client.get(f"/api/v1/admin/{kind}/{uuid4()}", headers=auth).status_code == 404
    for payload in ({}, {"email": "other@example.com"}, {"is_superuser": "false"}, {"is_active": None}):
        assert client.patch(f"/api/v1/admin/users/{normal.id}", headers=auth, json=payload).status_code == 422


def test_registration_cannot_assign_global_privileges(client):
    response = client.post("/api/v1/auth/register", json={
        "email": f"{uuid4()}@example.com", "password": "test-password", "display_name": "Normal",
        "is_superuser": True,
    })
    assert response.status_code == 201
    assert response.json()["user"]["is_superuser"] is False
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {response.json()['access_token']}"}).json()["is_superuser"] is False
