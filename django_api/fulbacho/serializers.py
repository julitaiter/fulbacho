from __future__ import annotations

from collections import Counter
from typing import Any

from django.db import transaction
from rest_framework import serializers

from .models import (
    Goal,
    Group,
    GroupMember,
    GroupRole,
    Match,
    MatchPlayer,
    Player,
    Team,
    User,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "display_name", "created_at"]
        read_only_fields = ["id", "created_at"]


class GroupSerializer(serializers.ModelSerializer):
    members_count = serializers.IntegerField(source="memberships.count", read_only=True)
    role = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ["id", "name", "code", "created_by", "created_at", "members_count", "role"]
        read_only_fields = ["id", "code", "created_by", "created_at", "members_count", "role"]

    def get_role(self, obj: Group) -> str | None:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        membership = obj.memberships.filter(user=user).first()
        return membership.role if membership else None

    def create(self, validated_data: dict[str, Any]) -> Group:
        request = self.context["request"]
        with transaction.atomic():
            group = Group.objects.create(created_by=request.user, **validated_data)
            GroupMember.objects.create(group=group, user=request.user, role=GroupRole.ADMIN)
        return group


class JoinGroupSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6)

    def validate_code(self, value: str) -> str:
        return value.strip().upper()

    def save(self, **kwargs) -> Group:
        request = self.context["request"]
        code = self.validated_data["code"]
        try:
            group = Group.objects.get(code=code)
        except Group.DoesNotExist as exc:
            raise serializers.ValidationError({"code": "No existe un grupo con ese codigo"}) from exc
        GroupMember.objects.get_or_create(
            group=group,
            user=request.user,
            defaults={"role": GroupRole.MEMBER},
        )
        return group


class PlayerSerializer(serializers.ModelSerializer):
    matches_played = serializers.IntegerField(read_only=True)
    goals_for = serializers.IntegerField(read_only=True)

    class Meta:
        model = Player
        fields = [
            "id",
            "group",
            "name",
            "linked_user",
            "active",
            "created_at",
            "matches_played",
            "goals_for",
        ]
        read_only_fields = ["id", "active", "created_at", "matches_played", "goals_for"]

    def validate_group(self, group: Group) -> Group:
        request = self.context.get("request")
        if request and request.user.is_authenticated and not group.is_member(request.user):
            raise serializers.ValidationError("No perteneces a este grupo")
        return group

    def validate_linked_user(self, linked_user: User | None) -> User | None:
        group = self.initial_data.get("group")
        if linked_user and group:
            if not GroupMember.objects.filter(group_id=group, user=linked_user).exists():
                raise serializers.ValidationError("El usuario vinculado debe ser miembro del grupo")
        return linked_user


class MatchPlayerSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source="player.name", read_only=True)

    class Meta:
        model = MatchPlayer
        fields = ["id", "player", "player_name", "team"]
        read_only_fields = ["id", "player_name"]


class GoalSerializer(serializers.ModelSerializer):
    player_name = serializers.CharField(source="player.name", read_only=True, allow_null=True)

    class Meta:
        model = Goal
        fields = ["id", "player", "player_name", "own_goal", "team_scored_for", "created_at"]
        read_only_fields = ["id", "player_name", "created_at"]


class MatchSerializer(serializers.ModelSerializer):
    participants = MatchPlayerSerializer(many=True, read_only=True)
    goals = GoalSerializer(many=True, read_only=True)
    editable_until = serializers.DateTimeField(read_only=True)
    can_be_edited = serializers.BooleanField(read_only=True)

    class Meta:
        model = Match
        fields = [
            "id",
            "group",
            "played_at",
            "modality",
            "location",
            "team_a_name",
            "team_b_name",
            "score_a",
            "score_b",
            "created_by",
            "created_at",
            "editable_until",
            "can_be_edited",
            "participants",
            "goals",
        ]
        read_only_fields = ["id", "created_by", "created_at", "editable_until", "can_be_edited"]


class MatchParticipantInputSerializer(serializers.Serializer):
    player_id = serializers.UUIDField()
    team = serializers.ChoiceField(choices=Team.choices)


class GoalInputSerializer(serializers.Serializer):
    player_id = serializers.UUIDField(required=False, allow_null=True)
    own_goal = serializers.BooleanField(default=False)
    team_scored_for = serializers.ChoiceField(choices=Team.choices)


class MatchCreateSerializer(serializers.ModelSerializer):
    participants = MatchParticipantInputSerializer(many=True, write_only=True)
    goals = GoalInputSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Match
        fields = [
            "id",
            "group",
            "played_at",
            "modality",
            "location",
            "team_a_name",
            "team_b_name",
            "score_a",
            "score_b",
            "participants",
            "goals",
        ]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.goal_warnings: list[str] = []
        self._players_by_id: dict[str, Player] = {}

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        request = self.context["request"]
        group: Group = attrs["group"]
        participants = attrs.get("participants", [])
        goals = attrs.get("goals", [])

        if not group.is_member(request.user):
            raise serializers.ValidationError({"group": "No perteneces a este grupo"})

        player_ids = [str(item["player_id"]) for item in participants]
        if len(player_ids) != len(set(player_ids)):
            raise serializers.ValidationError({"participants": "Un jugador no puede estar dos veces en el partido"})

        teams = Counter(item["team"] for item in participants)
        if teams[Team.A] < 2 or teams[Team.B] < 2:
            raise serializers.ValidationError({"participants": "Cada equipo necesita al menos 2 jugadores"})

        players = Player.objects.filter(id__in=player_ids, group=group, active=True)
        self._players_by_id = {str(player.id): player for player in players}
        missing = set(player_ids) - set(self._players_by_id.keys())
        if missing:
            raise serializers.ValidationError({"participants": "Hay jugadores inexistentes, inactivos o de otro grupo"})

        team_by_player_id = {str(item["player_id"]): item["team"] for item in participants}
        loaded_goals_by_team = Counter(item["team_scored_for"] for item in goals)
        if loaded_goals_by_team[Team.A] > attrs["score_a"] or loaded_goals_by_team[Team.B] > attrs["score_b"]:
            raise serializers.ValidationError({"goals": "La suma de goles cargados no puede superar el marcador final"})

        if loaded_goals_by_team[Team.A] < attrs["score_a"] or loaded_goals_by_team[Team.B] < attrs["score_b"]:
            self.goal_warnings.append("Hay goles del marcador final sin detalle de autor")

        for goal in goals:
            player_id = goal.get("player_id")
            own_goal = goal.get("own_goal", False)
            team_scored_for = goal["team_scored_for"]

            if own_goal and not player_id:
                raise serializers.ValidationError({"goals": "Un gol en contra debe tener jugador asignado"})

            if player_id:
                player_key = str(player_id)
                if player_key not in team_by_player_id:
                    raise serializers.ValidationError({"goals": "El autor del gol debe participar del partido"})

                player_team = team_by_player_id[player_key]
                if own_goal and player_team == team_scored_for:
                    raise serializers.ValidationError({"goals": "El gol en contra debe sumarse al equipo contrario"})
                if not own_goal and player_team != team_scored_for:
                    raise serializers.ValidationError({"goals": "El gol a favor debe sumarse al equipo del jugador"})

        return attrs

    def create(self, validated_data: dict[str, Any]) -> Match:
        request = self.context["request"]
        participants_data = validated_data.pop("participants")
        goals_data = validated_data.pop("goals", [])

        with transaction.atomic():
            match = Match.objects.create(created_by=request.user, **validated_data)
            MatchPlayer.objects.bulk_create(
                MatchPlayer(
                    match=match,
                    player=self._players_by_id[str(item["player_id"])],
                    team=item["team"],
                )
                for item in participants_data
            )
            Goal.objects.bulk_create(
                Goal(
                    match=match,
                    player=self._players_by_id.get(str(item.get("player_id"))) if item.get("player_id") else None,
                    own_goal=item.get("own_goal", False),
                    team_scored_for=item["team_scored_for"],
                )
                for item in goals_data
            )
        return match


class MatchUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Match
        fields = [
            "played_at",
            "modality",
            "location",
            "team_a_name",
            "team_b_name",
            "score_a",
            "score_b",
        ]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        match = self.instance
        score_a = attrs.get("score_a", match.score_a)
        score_b = attrs.get("score_b", match.score_b)
        goals_a = match.goals.filter(team_scored_for=Team.A).count()
        goals_b = match.goals.filter(team_scored_for=Team.B).count()
        if goals_a > score_a or goals_b > score_b:
            raise serializers.ValidationError("El nuevo marcador no puede ser menor a los goles ya cargados")
        return attrs
