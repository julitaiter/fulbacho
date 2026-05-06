from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from fulbacho.models import MatchModality, Team
from fulbacho.services import create_group, create_match


class Command(BaseCommand):
    help = "Carga datos demo para probar la webapp."

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="demo",
            defaults={
                "email": "demo@example.com",
                "display_name": "Demo",
            },
        )
        if created:
            user.set_password("demo12345")
            user.save()

        if user.group_memberships.exists():
            group = user.group_memberships.first().group
            self.stdout.write(self.style.WARNING(f"El usuario demo ya tenía grupo: {group.name} ({group.code})"))
            return

        group = create_group(user=user, name="Los del Jueves")
        names = ["El Toro", "Cebolla", "Nico", "Tincho", "Rama", "Pela", "Fede", "Gonza", "Chino", "Lucho"]
        players = [group.players.create(name=name) for name in names]

        create_match(
            created_by=user,
            validated_data={
                "group": group,
                "played_at": timezone.now(),
                "modality": MatchModality.FUTBOL5,
                "location": "La 10",
                "team_a_name": "Los Cracks",
                "team_b_name": "El Desastre",
                "score_a": 5,
                "score_b": 3,
                "team_a_players": [p.id for p in players[:5]],
                "team_b_players": [p.id for p in players[5:]],
                "goals": [
                    {"player": players[0], "team_scored_for": Team.A, "own_goal": False},
                    {"player": players[1], "team_scored_for": Team.A, "own_goal": False},
                    {"player": players[0], "team_scored_for": Team.A, "own_goal": False},
                    {"player": players[6], "team_scored_for": Team.B, "own_goal": False},
                    {"player": players[7], "team_scored_for": Team.B, "own_goal": False},
                    {"player": players[8], "team_scored_for": Team.A, "own_goal": True},
                ],
            },
        )

        self.stdout.write(self.style.SUCCESS("Demo cargada. Usuario: demo / clave: demo12345"))
        self.stdout.write(self.style.SUCCESS(f"Grupo: {group.name} / código: {group.code}"))
