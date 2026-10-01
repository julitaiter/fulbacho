from urllib.parse import quote

from .client import ApiClient


class AuthAPI:
    def __init__(self, client: ApiClient): self.client = client
    def register(self, **payload): return self.client.post("/auth/register", json=payload, auth=False)
    def login(self, **payload): return self.client.post("/auth/login", json=payload, auth=False)
    def me(self): return self.client.get("/auth/me")
    def logout(self, refresh_token): return self.client.post("/auth/logout", json={"refresh_token": refresh_token}, auth=False)


class GroupsAPI:
    def __init__(self, client): self.client = client
    def list(self): return self.client.get("/groups")
    def overview(self): return self.client.get("/groups/overview")
    def create(self, name): return self.client.post("/groups", json={"name": name})
    def join(self, code): return self.client.post("/groups/join", json={"code": code})
    def get(self, group_id): return self.client.get(f"/groups/{group_id}")
    def update(self, group_id, name): return self.client.patch(f"/groups/{group_id}", json={"name": name})
    def members(self, group_id): return self.client.get(f"/groups/{group_id}/members")
    def set_member_role(self, group_id, user_id, role): return self.client.patch(f"/groups/{group_id}/members/{user_id}", json={"role": role})
    def remove_member(self, group_id, user_id): return self.client.delete(f"/groups/{group_id}/members/{user_id}")


class PlayersAPI:
    def __init__(self, client): self.client = client
    def list(self, group_id, include_inactive=False): return self.client.get(f"/groups/{group_id}/players", params={"include_inactive": str(include_inactive).lower()})
    def get(self, group_id, player_id): return self.client.get(f"/groups/{group_id}/players/{player_id}")
    def create(self, group_id, payload): return self.client.post(f"/groups/{group_id}/players", json=payload)
    def update(self, group_id, player_id, payload): return self.client.patch(f"/groups/{group_id}/players/{player_id}", json=payload)
    def deactivate(self, group_id, player_id): return self.client.delete(f"/groups/{group_id}/players/{player_id}")
    def casuals(self, group_id): return self.client.get(f"/groups/{group_id}/players/casuals")
    def promote_casual(self, group_id, payload): return self.client.post(f"/groups/{group_id}/players/promote-casual", json=payload)
    def attach_casual(self, group_id, player_id, participant_ids): return self.client.post(f"/groups/{group_id}/players/{player_id}/attach-casual", json={"participant_ids": participant_ids})


class MatchesAPI:
    def __init__(self, client): self.client = client
    def list(self, group_id, **params): return self.client.get(f"/groups/{group_id}/matches", params={k: v for k, v in params.items() if v is not None})
    def get(self, group_id, match_id): return self.client.get(f"/groups/{group_id}/matches/{match_id}")
    def create(self, group_id, payload): return self.client.post(f"/groups/{group_id}/matches", json=payload)
    def update(self, group_id, match_id, payload): return self.client.put(f"/groups/{group_id}/matches/{match_id}", json=payload)


class StatsAPI:
    def __init__(self, client): self.client = client
    def summary(self, group_id): return self.client.get(f"/groups/{group_id}/stats/summary")
    def rankings(self, group_id, limit=10): return self.client.get(f"/groups/{group_id}/stats/rankings", params={"limit": limit})
    def players(self, group_id): return self.client.get(f"/groups/{group_id}/stats/players")
    def player(self, group_id, player_id): return self.client.get(f"/groups/{group_id}/stats/players/{player_id}")


class GuestAPI:
    def __init__(self, client): self.client = client
    def group(self, code): return self.client.get(f"/guest/{quote(code) }", auth=False)
    def players(self, code): return self.client.get(f"/guest/{quote(code)}/players", auth=False)
    def player(self, code, player_id): return self.client.get(f"/guest/{quote(code)}/players/{player_id}", auth=False)
    def player_stats(self, code, player_id): return self.client.get(f"/guest/{quote(code)}/players/{player_id}/stats", auth=False)
    def matches(self, code, **params): return self.client.get(f"/guest/{quote(code)}/matches", params={k: v for k, v in params.items() if v is not None}, auth=False)
    def match(self, code, match_id): return self.client.get(f"/guest/{quote(code)}/matches/{match_id}", auth=False)
    def summary(self, code): return self.client.get(f"/guest/{quote(code)}/stats/summary", auth=False)
    def rankings(self, code, limit=10): return self.client.get(f"/guest/{quote(code)}/stats/rankings", params={"limit": limit}, auth=False)
    def player_stats_list(self, code): return self.client.get(f"/guest/{quote(code)}/stats/players", auth=False)


class AdminAPI:
    def __init__(self, client):
        self.client = client

    def users(self, *, offset=0, limit=50):
        return self.client.get("/admin/users", params={"offset": offset, "limit": limit})

    def user(self, user_id):
        return self.client.get(f"/admin/users/{user_id}")

    def update_user(self, user_id, **values):
        return self.client.patch(f"/admin/users/{user_id}", json=values)

    def groups(self, *, offset=0, limit=50):
        return self.client.get("/admin/groups", params={"offset": offset, "limit": limit})

    def group(self, group_id):
        return self.client.get(f"/admin/groups/{group_id}")

    def members(self, group_id):
        return self.client.get(f"/admin/groups/{group_id}/members")

    def matches(self, *, offset=0, limit=50):
        return self.client.get("/admin/matches", params={"offset": offset, "limit": limit})

    def match(self, match_id):
        return self.client.get(f"/admin/matches/{match_id}")


class FulbachoAPI:
    def __init__(self, django_request=None):
        self.client = ApiClient(django_request)
        self.auth = AuthAPI(self.client)
        self.admin = AdminAPI(self.client)
        self.groups = GroupsAPI(self.client)
        self.players = PlayersAPI(self.client)
        self.matches = MatchesAPI(self.client)
        self.stats = StatsAPI(self.client)
        self.guest = GuestAPI(self.client)
