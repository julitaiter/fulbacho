from datetime import UTC, datetime
from unittest.mock import Mock, patch
from uuid import UUID

from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, SimpleTestCase, override_settings

from fulbacho.forms import MatchForm
from fulbacho.views import (
    _build_match_payload,
    _initial_match_form,
    _match_editor,
    _participant_editor_rows,
)


PLAYER_1 = {"id": "11111111-1111-1111-1111-111111111111", "name": "Ana", "active": True}
PLAYER_2 = {"id": "22222222-2222-2222-2222-222222222222", "name": "Beto", "active": True}
PLAYERS = [PLAYER_1, PLAYER_2]


def match_form_data(minimum=1, **overrides):
    data = {
        "played_at": "2026-09-28T20:00",
        "players_per_team": str(minimum),
        "location": "La cancha",
        "team_a_name": "Verdes",
        "team_b_name": "Negros",
        "score_a": "3",
        "score_b": "2",
    }
    data.update(overrides)
    return data


def add_participant(data, side, index, name, player_id="", goals=0, own_goals=0):
    data[f"participant_{side}_name_{index}"] = name
    data[f"participant_{side}_player_id_{index}"] = player_id
    data[f"participant_{side}_goals_{index}"] = str(goals)
    data[f"participant_{side}_own_goals_{index}"] = str(own_goals)


def payload_for(data, players=PLAYERS):
    request = RequestFactory().post("/partido/", data)
    form = MatchForm(data)
    assert form.is_valid(), form.errors
    return _build_match_payload(request, form, players)


def request_with_messages(method="post", data=None):
    factory = RequestFactory()
    request = getattr(factory, method)("/partido/", data or {})
    SessionMiddleware(lambda django_request: None).process_request(request)
    request.session.save()
    MessageMiddleware(lambda django_request: None).process_request(request)
    return request


@override_settings(SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies")
class MatchEditorTests(SimpleTestCase):
    def test_initial_match_form_accepts_api_normalized_datetime(self):
        match = {
            "played_at": datetime(2026, 9, 28, 23, 45, tzinfo=UTC),
            "players_per_team": 5,
            "location": None,
            "team_a_name": "Verdes",
            "team_b_name": "Negros",
            "score_a": 2,
            "score_b": 1,
        }

        initial = _initial_match_form(match)

        self.assertEqual(initial["played_at"], "2026-09-28T20:45")
        self.assertEqual(initial["location"], "")

    def test_initial_match_form_remains_compatible_with_iso_string(self):
        match = {
            "played_at": "2026-09-28T20:45:00-03:00",
            "players_per_team": 5,
            "location": "Cancha 1",
            "team_a_name": "Verdes",
            "team_b_name": "Negros",
            "score_a": 2,
            "score_b": 1,
        }

        initial = _initial_match_form(match)

        self.assertEqual(initial["played_at"], "2026-09-28T20:45")

    def test_format_sets_minimum_slots_for_both_teams(self):
        request = RequestFactory().get("/partido/")

        rows = _participant_editor_rows(PLAYERS, request, minimum=6)

        self.assertEqual(len(rows["A"]), 6)
        self.assertEqual(len(rows["B"]), 6)
        self.assertTrue(all(row["name"] == "" for row in rows["A"] + rows["B"]))

    def test_edit_preserves_regular_casual_extra_teams_and_goals(self):
        match = {
            "participants": [
                {
                    "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "player_id": PLAYER_1["id"],
                    "display_name": "Ana",
                    "team": "A",
                },
                {
                    "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "player_id": None,
                    "display_name": "Ana",
                    "team": "A",
                },
                {
                    "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                    "player_id": None,
                    "display_name": "Cami",
                    "team": "B",
                },
            ],
            "goals": [
                {"participant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "own_goal": False},
                {"participant_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "own_goal": True},
            ],
        }

        rows = _participant_editor_rows(PLAYERS, RequestFactory().get("/partido/"), match, 1)

        self.assertEqual(len(rows["A"]), 2)
        self.assertEqual(rows["A"][0]["player_id"], PLAYER_1["id"])
        self.assertEqual(rows["A"][0]["goals_for"], 1)
        self.assertEqual(rows["A"][1]["player_id"], "")
        self.assertEqual(rows["A"][1]["name"], "Ana")
        self.assertEqual(rows["A"][1]["own_goals"], 1)
        self.assertEqual(rows["B"][0]["name"], "Cami")

    def test_serializes_regular_casual_and_extra_participants(self):
        data = match_form_data(minimum=1)
        add_participant(data, "A", 0, "Ana", PLAYER_1["id"], goals=2)
        add_participant(data, "A", 1, "Invitado", goals=1)
        add_participant(data, "B", 0, "Beto", PLAYER_2["id"], own_goals=1)
        add_participant(data, "B", 1, "Invitado")

        payload = payload_for(data)

        self.assertEqual(payload["team_a"]["participants"], [
            {"ref": f"p-{PLAYER_1['id']}", "player_id": PLAYER_1["id"]},
            {"ref": "c-a-1", "name": "Invitado"},
        ])
        self.assertEqual(payload["team_b"]["participants"], [
            {"ref": f"p-{PLAYER_2['id']}", "player_id": PLAYER_2["id"]},
            {"ref": "c-b-1", "name": "Invitado"},
        ])
        self.assertEqual(len(payload["goals"]), 4)
        self.assertEqual(payload["goals"][-1], {
            "participant_ref": f"p-{PLAYER_2['id']}",
            "own_goal": True,
        })

    def test_edited_regular_name_is_serialized_as_casual(self):
        data = match_form_data()
        add_participant(data, "A", 0, "Ana editada", PLAYER_1["id"])
        add_participant(data, "B", 0, "Beto", PLAYER_2["id"])

        payload = payload_for(data)

        self.assertEqual(payload["team_a"]["participants"], [
            {"ref": "c-a-0", "name": "Ana editada"}
        ])

    def test_does_not_infer_regular_player_from_matching_casual_name(self):
        data = match_form_data()
        add_participant(data, "A", 0, "Ana")
        add_participant(data, "B", 0, "Ana")

        payload = payload_for(data)

        self.assertNotIn("player_id", payload["team_a"]["participants"][0])
        self.assertNotIn("player_id", payload["team_b"]["participants"][0])

    def test_rejects_duplicate_regular_player_across_teams(self):
        data = match_form_data()
        add_participant(data, "A", 0, "Ana", PLAYER_1["id"])
        add_participant(data, "B", 0, "Ana", PLAYER_1["id"])

        with self.assertRaisesMessage(ValueError, "Ana no puede aparecer más de una vez"):
            payload_for(data)

    def test_requires_filled_minimum_and_ignores_goals_for_removed_slots(self):
        data = match_form_data(minimum=2)
        add_participant(data, "A", 0, "Ana", PLAYER_1["id"])
        add_participant(data, "B", 0, "Beto", PLAYER_2["id"])
        add_participant(data, "B", 1, "Casual")
        data["participant_A_goals_99"] = "4"

        with self.assertRaisesMessage(ValueError, "Equipo A requiere al menos 2"):
            payload_for(data)

        add_participant(data, "A", 1, "Extra")
        payload = payload_for(data)
        self.assertFalse(any(goal["participant_ref"].endswith("99") for goal in payload["goals"]))

    def test_edit_form_renders_both_teams_and_preserves_casual_identity(self):
        match = {
            "id": "44444444-4444-4444-4444-444444444444",
            "played_at": "2026-09-28T20:00:00-03:00",
            "players_per_team": 1,
            "location": "",
            "team_a_name": "Verdes",
            "team_b_name": "Negros",
            "score_a": 1,
            "score_b": 0,
            "participants": [
                {
                    "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "player_id": PLAYER_1["id"],
                    "display_name": "Ana",
                    "team": "A",
                },
                {
                    "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                    "player_id": None,
                    "display_name": "Ana",
                    "team": "A",
                },
                {
                    "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                    "player_id": None,
                    "display_name": "Cami",
                    "team": "B",
                },
            ],
            "goals": [],
        }
        request = request_with_messages(method="get")
        api = Mock()
        api.groups.get.return_value = {
            "id": "33333333-3333-3333-3333-333333333333",
            "name": "Grupo",
        }
        api.players.list.return_value = PLAYERS
        api.matches.get.return_value = match
        group_id = UUID("33333333-3333-3333-3333-333333333333")
        match_id = UUID(match["id"])

        with patch("fulbacho.views.api_for", return_value=api):
            response = _match_editor(request, group_id, match_id)

        content = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(content.count('class="participant-slot"'), 3)
        self.assertIn('data-team="A"', content)
        self.assertIn('data-team="B"', content)
        self.assertIn(f'value="{PLAYER_1["id"]}" data-player-id', content)
        self.assertIn('value="Ana" maxlength="100"', content)
        self.assertNotIn("Jugadores casuales", content)
        self.assertNotIn("goal-editor-panel", content)
        self.assertNotIn("participant-kind", content)
        self.assertIn("A favor", content)
        self.assertIn("En contra", content)
        self.assertIn('data-goals-input', content)
        self.assertIn('/static/js/match-form.js', content)

    def test_final_payload_is_sent_unchanged_to_fastapi_client(self):
        data = match_form_data()
        add_participant(data, "A", 0, "Ana", PLAYER_1["id"], goals=1)
        add_participant(data, "B", 0, "Casual B")
        request = request_with_messages(data=data)
        api = Mock()
        api.groups.get.return_value = {"id": "33333333-3333-3333-3333-333333333333", "name": "Grupo"}
        api.players.list.return_value = PLAYERS
        api.matches.create.return_value = {"id": "44444444-4444-4444-4444-444444444444"}
        group_id = UUID("33333333-3333-3333-3333-333333333333")

        with patch("fulbacho.views.api_for", return_value=api):
            response = _match_editor(request, group_id)

        self.assertEqual(response.status_code, 302)
        sent = api.matches.create.call_args.args[1]
        self.assertEqual(sent["team_a"]["participants"][0]["player_id"], PLAYER_1["id"])
        self.assertEqual(sent["team_b"]["participants"][0], {
            "ref": "c-b-0",
            "name": "Casual B",
        })
        self.assertEqual(sent["goals"], [{
            "participant_ref": f"p-{PLAYER_1['id']}",
            "own_goal": False,
        }])
