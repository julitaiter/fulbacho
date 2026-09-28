def test_register_login_and_me(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "juli@example.com", "password": "supersecret", "display_name": "Juli"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user"]["email"] == "juli@example.com"
    access = data["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["display_name"] == "Juli"
