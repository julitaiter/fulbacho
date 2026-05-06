from __future__ import annotations

from datetime import timedelta
import random
import string
import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


CODE_ALPHABET = string.ascii_uppercase + string.digits


class Team(models.TextChoices):
    A = "A", "Equipo A"
    B = "B", "Equipo B"


class GroupRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    MEMBER = "member", "Miembro"


class MatchModality(models.TextChoices):
    FUTBOL5 = "futbol5", "Futbol 5"
    FUTBOL6 = "futbol6", "Futbol 6"


class User(AbstractUser):
    """Usuario Django adaptado al concepto de profiles de la especificacion original."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "profiles"
        verbose_name = "perfil"
        verbose_name_plural = "perfiles"

    def __str__(self) -> str:
        return self.display_name or self.username or self.email


class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=6, unique=True, editable=False)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_groups",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "groups"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs) -> None:
        if not self.code:
            self.code = self.generate_unique_code()
        super().save(*args, **kwargs)

    @classmethod
    def generate_unique_code(cls) -> str:
        for _ in range(100):
            code = "".join(random.choices(CODE_ALPHABET, k=6))
            if not cls.objects.filter(code=code).exists():
                return code
        raise RuntimeError("No se pudo generar un codigo unico de grupo")

    def is_member(self, user: User) -> bool:
        return self.memberships.filter(user=user).exists()

    def is_admin(self, user: User) -> bool:
        return self.memberships.filter(user=user, role=GroupRole.ADMIN).exists()


class GroupMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="group_memberships")
    role = models.CharField(max_length=10, choices=GroupRole.choices, default=GroupRole.MEMBER)
    joined_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "group_members"
        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="uniq_group_member"),
        ]
        ordering = ["joined_at"]

    def __str__(self) -> str:
        return f"{self.user} -> {self.group} ({self.role})"


class Player(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="players")
    name = models.CharField(max_length=120)
    linked_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="linked_players",
        null=True,
        blank=True,
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "players"
        constraints = [
            models.UniqueConstraint(fields=["group", "name"], name="uniq_player_name_per_group"),
        ]
        ordering = ["name"]

    def __str__(self) -> str:
        suffix = "" if self.active else " (baja)"
        return f"{self.name}{suffix}"


class Match(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="matches")
    played_at = models.DateTimeField(default=timezone.now)
    modality = models.CharField(max_length=10, choices=MatchModality.choices)
    location = models.CharField(max_length=160, blank=True, null=True)
    team_a_name = models.CharField(max_length=80, default="Equipo A")
    team_b_name = models.CharField(max_length=80, default="Equipo B")
    score_a = models.PositiveIntegerField(default=0)
    score_b = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_matches",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "matches"
        ordering = ["-played_at", "-created_at"]

    def __str__(self) -> str:
        return f"{self.team_a_name} {self.score_a}-{self.score_b} {self.team_b_name}"

    @property
    def editable_until(self):
        return self.created_at + timedelta(hours=24)

    def can_be_edited(self) -> bool:
        return timezone.now() <= self.editable_until

    def clean(self) -> None:
        if self.score_a < 0 or self.score_b < 0:
            raise ValidationError("El marcador no puede tener valores negativos")


class MatchPlayer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="participants")
    player = models.ForeignKey(Player, on_delete=models.PROTECT, related_name="match_entries")
    team = models.CharField(max_length=1, choices=Team.choices)

    class Meta:
        db_table = "match_players"
        constraints = [
            models.UniqueConstraint(fields=["match", "player"], name="uniq_player_once_per_match"),
        ]
        ordering = ["team", "player__name"]

    def __str__(self) -> str:
        return f"{self.player} en {self.team}"

    def clean(self) -> None:
        if self.player_id and self.match_id and self.player.group_id != self.match.group_id:
            raise ValidationError("El jugador debe pertenecer al mismo grupo que el partido")


class Goal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="goals")
    player = models.ForeignKey(
        Player,
        on_delete=models.SET_NULL,
        related_name="goals",
        null=True,
        blank=True,
    )
    own_goal = models.BooleanField(default=False)
    team_scored_for = models.CharField(max_length=1, choices=Team.choices)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "goals"
        ordering = ["created_at"]

    def __str__(self) -> str:
        scorer = self.player.name if self.player else "Anonimo"
        suffix = " en contra" if self.own_goal else ""
        return f"Gol de {scorer}{suffix} para {self.team_scored_for}"

    def clean(self) -> None:
        errors = {}
        if self.own_goal and not self.player_id:
            errors["player"] = "Un gol en contra debe tener jugador asignado"

        if self.player_id and self.match_id:
            participant = MatchPlayer.objects.filter(match=self.match, player=self.player).first()
            if not participant:
                errors["player"] = "El jugador debe participar del partido"
            else:
                if self.own_goal and self.team_scored_for == participant.team:
                    errors["team_scored_for"] = "El gol en contra se suma al equipo contrario"
                if not self.own_goal and self.team_scored_for != participant.team:
                    errors["team_scored_for"] = "El gol a favor se suma al equipo del jugador"

        if errors:
            raise ValidationError(errors)
