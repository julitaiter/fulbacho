def _register(client, email="web@example.com", display_name="Web User"):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "supersecret", "display_name": display_name},
    )
    assert response.status_code == 201
    return response.json(), {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_group_overview_has_counts_and_role(client):
    _, headers = _register(client)
    group = client.post("/api/v1/groups", json={"name": "Jueves"}, headers=headers).json()
    client.post(
        f"/api/v1/groups/{group['id']}/players",
        json={"name": "Juli", "linked_user_id": None},
        headers=headers,
    )

    response = client.get("/api/v1/groups/overview", headers=headers)
    assert response.status_code == 200
    item = response.json()[0]
    assert item["players_count"] == 1
    assert item["matches_count"] == 0
    assert item["role"] == "admin"


def test_guest_player_stats_and_promote_casual(client):
    _, headers = _register(client, "casual@example.com")
    group = client.post("/api/v1/groups", json={"name": "Casuales"}, headers=headers).json()

    payload = {
        "played_at": "2026-09-18T21:00:00-03:00",
        "players_per_team": 5,
        "team_a": {
            "name": "A",
            "score": 1,
            "participants": [{"ref": "casual", "name": "Fede"}] + [
                {"ref": f"ac{i}", "name": f"A{i}"} for i in range(4)
            ],
        },
        "team_b": {
            "name": "B",
            "score": 0,
            "participants": [{"ref": f"bc{i}", "name": f"B{i}"} for i in range(5)],
        },
        "goals": [{"participant_ref": "casual", "own_goal": False}],
    }
    match = client.post(
        f"/api/v1/groups/{group['id']}/matches", json=payload, headers=headers
    )
    assert match.status_code == 201

    casuals = client.get(
        f"/api/v1/groups/{group['id']}/players/casuals", headers=headers
    ).json()
    fede = next(item for item in casuals if item["display_name"] == "Fede")
    promoted = client.post(
        f"/api/v1/groups/{group['id']}/players/promote-casual",
        headers=headers,
        json={"name": "Fede", "participant_ids": [fede["id"]], "linked_user_id": None},
    )
    assert promoted.status_code == 201
    player = promoted.json()

    guest_stats = client.get(
        f"/api/v1/guest/{group['code']}/players/{player['id']}/stats"
    )
    assert guest_stats.status_code == 200
    assert guest_stats.json()["matches_played"] == 1
    assert guest_stats.json()["goals_for"] == 1

    guest_matches = client.get(
        f"/api/v1/guest/{group['code']}/matches", params={"player_id": player["id"]}
    )
    assert guest_matches.status_code == 200
    assert len(guest_matches.json()) == 1
