import secrets
import string
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=150, blank=True)

    def __str__(self) -> str:
        return self.display_name or self.email or self.username


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class GroupRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Miembro"


class MatchModality(models.TextChoices):
    FUTBOL5 = "futbol5", "Fútbol 5"
    FUTBOL6 = "futbol6", "Fútbol 6"


class Team(models.TextChoices):
    A = "A", "Equipo A"
    B = "B", "Equipo B"


class FriendGroup(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=6, unique=True, editable=False, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_groups",
    )

    class Meta:
        db_table = "groups"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_unique_code()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("group-dashboard", args=[self.id])

    @classmethod
    def generate_unique_code(cls) -> str:
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(20):
            code = "".join(secrets.choice(alphabet) for _ in range(6))
            if not cls.objects.filter(code=code).exists():
                return code
        raise RuntimeError("No se pudo generar un código único de grupo.")


class GroupMember(models.Model):
    group = models.ForeignKey(FriendGroup, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="group_memberships",
    )
    role = models.CharField(max_length=20, choices=GroupRole.choices, default=GroupRole.MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "group_members"
        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="uniq_group_member"),
        ]

    def __str__(self) -> str:
        return f"{self.user} en {self.group} como {self.role}"


class Player(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(FriendGroup, on_delete=models.CASCADE, related_name="players")
    name = models.CharField(max_length=120)
    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="linked_players",
    )
    active = models.BooleanField(default=True)

    class Meta:
        db_table = "players"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["group", "name"], name="uniq_player_name_per_group"),
        ]

    def __str__(self) -> str:
        return self.name


class Match(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(FriendGroup, on_delete=models.CASCADE, related_name="matches")
    played_at = models.DateTimeField(default=timezone.now)
    modality = models.CharField(max_length=20, choices=MatchModality.choices)
    location = models.CharField(max_length=160, blank=True)
    team_a_name = models.CharField(max_length=120, default="Equipo A")
    team_b_name = models.CharField(max_length=120, default="Equipo B")
    score_a = models.PositiveIntegerField(default=0)
    score_b = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_matches",
    )

    class Meta:
        db_table = "matches"
        ordering = ["-played_at"]
        indexes = [
            models.Index(fields=["group", "played_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.team_a_name} {self.score_a}-{self.score_b} {self.team_b_name}"

    @property
    def can_be_edited(self) -> bool:
        return timezone.now() <= self.created_at + timedelta(hours=24)

    @property
    def total_score_goals(self) -> int:
        return self.score_a + self.score_b

    def clean(self) -> None:
        if self.score_a < 0 or self.score_b < 0:
            raise ValidationError("Los marcadores no pueden ser negativos.")


class MatchPlayer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="match_players")
    player = models.ForeignKey(Player, on_delete=models.PROTECT, related_name="match_players")
    team = models.CharField(max_length=1, choices=Team.choices)

    class Meta:
        db_table = "match_players"
        constraints = [
            models.UniqueConstraint(fields=["match", "player"], name="uniq_player_once_per_match"),
        ]

    def __str__(self) -> str:
        return f"{self.player} - {self.team}"

    def clean(self) -> None:
        if self.player.group_id != self.match.group_id:
            raise ValidationError("El jugador debe pertenecer al mismo grupo que el partido.")


class Goal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="goals")
    player = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="goals",
    )
    own_goal = models.BooleanField(default=False)
    team_scored_for = models.CharField(max_length=1, choices=Team.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "goals"
        indexes = [
            models.Index(fields=["match", "team_scored_for"]),
            models.Index(fields=["player", "own_goal"]),
        ]

    def __str__(self) -> str:
        player = self.player.name if self.player else "Gol sin asignar"
        suffix = " (en contra)" if self.own_goal else ""
        return f"{player}{suffix} -> {self.team_scored_for}"

    def clean(self) -> None:
        if self.player and self.player.group_id != self.match.group_id:
            raise ValidationError("El jugador del gol debe pertenecer al grupo del partido.")
