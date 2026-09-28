def _register(client, email="owner@example.com"):
    data = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "supersecret", "display_name": "Owner"},
    ).json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def test_f5_requires_five_players_per_team(client):
    headers = _register(client)
    group = client.post("/api/v1/groups", json={"name": "Los del Jueves"}, headers=headers).json()
    payload = {
        "played_at": "2026-09-17T21:00:00-03:00",
        "players_per_team": 5,
        "team_a": {
            "name": "A",
            "score": 0,
            "participants": [{"ref": f"a{i}", "name": f"A{i}"} for i in range(4)],
        },
        "team_b": {
            "name": "B",
            "score": 0,
            "participants": [{"ref": f"b{i}", "name": f"B{i}"} for i in range(5)],
        },
        "goals": [],
    }
    response = client.post(f"/api/v1/groups/{group['id']}/matches", json=payload, headers=headers)
    assert response.status_code == 409


def test_anonymous_goals_fill_score_and_draw_is_valid(client):
    headers = _register(client)
    group = client.post("/api/v1/groups", json={"name": "Grupo"}, headers=headers).json()
    payload = {
        "played_at": "2026-09-17T21:00:00-03:00",
        "players_per_team": 5,
        "team_a": {"name": "A", "score": 2, "participants": [{"ref": f"a{i}", "name": f"A{i}"} for i in range(5)]},
        "team_b": {"name": "B", "score": 2, "participants": [{"ref": f"b{i}", "name": f"B{i}"} for i in range(5)]},
        "goals": [{"participant_ref": "a0", "own_goal": False}],
    }
    response = client.post(f"/api/v1/groups/{group['id']}/matches", json=payload, headers=headers)
    assert response.status_code == 201
    body = response.json()
    assert body["score_a"] == 2
    assert body["score_b"] == 2
    assert len(body["goals"]) == 4
