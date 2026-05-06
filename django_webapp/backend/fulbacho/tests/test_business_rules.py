from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from fulbacho.models import MatchModality, Team
from fulbacho.services import create_group, create_match


class MatchRulesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="test12345",
        )
        self.group = create_group(user=self.user, name="Test Group")
        self.players = [
            self.group.players.create(name=f"Jugador {idx}")
            for idx in range(1, 7)
        ]

    def base_payload(self):
        return {
            "group": self.group,
            "modality": MatchModality.FUTBOL5,
            "location": "",
            "team_a_name": "A",
            "team_b_name": "B",
            "score_a": 2,
            "score_b": 1,
            "team_a_players": [self.players[0].id, self.players[1].id],
            "team_b_players": [self.players[2].id, self.players[3].id],
            "goals": [
                {"player": self.players[0], "team_scored_for": Team.A, "own_goal": False},
            ],
        }

    def test_player_cannot_be_in_both_teams(self):
        payload = self.base_payload()
        payload["team_b_players"] = [self.players[0].id, self.players[2].id]
        with self.assertRaises(ValidationError):
            create_match(created_by=self.user, validated_data=payload)

    def test_loaded_goals_cannot_exceed_score(self):
        payload = self.base_payload()
        payload["goals"] = [
            {"player": self.players[0], "team_scored_for": Team.A, "own_goal": False},
            {"player": self.players[1], "team_scored_for": Team.A, "own_goal": False},
            {"player": self.players[0], "team_scored_for": Team.A, "own_goal": False},
        ]
        with self.assertRaises(ValidationError):
            create_match(created_by=self.user, validated_data=payload)

    def test_valid_match_can_be_created(self):
        match = create_match(created_by=self.user, validated_data=self.base_payload())
        self.assertEqual(match.match_players.count(), 4)
        self.assertEqual(match.goals.count(), 1)
