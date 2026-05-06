from django.test import TestCase

from .models import Group, GroupMember, GroupRole, Match, MatchModality, Player, User


class FulbachoModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="secret12345",
            display_name="Admin",
        )
        self.group = Group.objects.create(name="Los del Jueves", created_by=self.user)
        GroupMember.objects.create(group=self.group, user=self.user, role=GroupRole.ADMIN)

    def test_group_generates_six_character_code(self):
        self.assertEqual(len(self.group.code), 6)

    def test_match_edit_window_is_open_after_creation(self):
        match = Match.objects.create(
            group=self.group,
            modality=MatchModality.FUTBOL5,
            team_a_name="A",
            team_b_name="B",
            score_a=1,
            score_b=0,
            created_by=self.user,
        )
        self.assertTrue(match.can_be_edited())

    def test_player_belongs_to_group(self):
        player = Player.objects.create(group=self.group, name="El Toro")
        self.assertEqual(player.group, self.group)
