from unittest.mock import Mock

from django.test import SimpleTestCase

from fulbacho.views import _dashboard, _ranking_highlight


class RankingHighlightTests(SimpleTestCase):
    def test_single_leader_uses_its_name(self):
        highlight = _ranking_highlight(
            [{"name": "Ana", "goals_for": 8}, {"name": "Beto", "goals_for": 5}],
            "goals_for",
        )

        self.assertEqual(highlight["display_name"], "Ana")
        self.assertEqual(highlight["leaders_count"], 1)

    def test_exactly_two_leaders_uses_both_names(self):
        highlight = _ranking_highlight(
            [{"name": "Ana", "goals_for": 8}, {"name": "Beto", "goals_for": 8}],
            "goals_for",
        )

        self.assertEqual(highlight["display_name"], "Ana y Beto")
        self.assertEqual(highlight["leaders_count"], 2)

    def test_more_than_two_leaders_uses_people_count(self):
        highlight = _ranking_highlight(
            [
                {"name": "Ana", "goals_for": 8},
                {"name": "Beto", "goals_for": 8},
                {"name": "Cami", "goals_for": 8},
                {"name": "Dani", "goals_for": 7},
            ],
            "goals_for",
        )

        self.assertEqual(highlight["display_name"], "3 personas")
        self.assertEqual(highlight["leaders_count"], 3)
        self.assertEqual(highlight["goals_for"], 8)

    def test_empty_ranking_has_no_highlight(self):
        self.assertIsNone(_ranking_highlight([], "goals_for"))
        self.assertIsNone(_ranking_highlight(None, "goals_for"))

    def test_group_dashboard_applies_ties_to_every_highlight(self):
        api = Mock()
        api.stats.summary.return_value = {
            "most_scored_match": None,
            "last_match": None,
        }
        api.stats.players.return_value = []
        api.stats.rankings.return_value = {
            "minimum_matches_for_win_rate": 2,
            "top_scorers": [
                {"name": "Ana", "goals_for": 4},
                {"name": "Beto", "goals_for": 4},
            ],
            "own_goal_kings": [
                {"name": "Ana", "own_goals": 1},
                {"name": "Beto", "own_goals": 1},
                {"name": "Cami", "own_goals": 1},
            ],
            "most_participative": [{"name": "Cami", "matches_played": 9}],
            "best_win_rate": [
                {"name": "Ana", "win_rate": 75.0},
                {"name": "Cami", "win_rate": 75.0},
            ],
            "active_streaks": [
                {"name": "Ana", "current_win_streak": 2},
                {"name": "Beto", "current_win_streak": 2},
                {"name": "Cami", "current_win_streak": 2},
                {"name": "Dani", "current_win_streak": 2},
            ],
        }

        dashboard = _dashboard(api, group_id="group-id")

        api.stats.rankings.assert_called_once_with("group-id", limit=100)
        self.assertEqual(dashboard["rankings"]["top_scorer"]["display_name"], "Ana y Beto")
        self.assertEqual(dashboard["rankings"]["own_goal_king"]["display_name"], "3 personas")
        self.assertEqual(dashboard["rankings"]["most_participative"]["display_name"], "Cami")
        self.assertEqual(dashboard["rankings"]["best_win_rate"]["display_name"], "Ana y Cami")
        self.assertEqual(
            dashboard["rankings"]["active_streak_leader"]["display_name"],
            "4 personas",
        )
