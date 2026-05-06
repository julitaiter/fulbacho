from __future__ import annotations

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Goal, Group, GroupRole, Match, Player
from .serializers import (
    GroupSerializer,
    JoinGroupSerializer,
    MatchCreateSerializer,
    MatchSerializer,
    MatchUpdateSerializer,
    PlayerSerializer,
)
from .stats import group_dashboard, player_stats


class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return (
            Group.objects.filter(memberships__user=self.request.user)
            .prefetch_related("memberships")
            .distinct()
        )

    def perform_update(self, serializer):
        group = self.get_object()
        if not group.is_admin(self.request.user):
            raise PermissionDenied("Solo un admin puede modificar el grupo")
        serializer.save()

    @action(detail=False, methods=["post"], url_path="join")
    def join(self, request):
        serializer = JoinGroupSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        group = serializer.save()
        return Response(GroupSerializer(group, context={"request": request}).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="dashboard")
    def dashboard(self, request, pk=None):
        group = self.get_object()
        return Response(group_dashboard(group))


class PlayerViewSet(viewsets.ModelViewSet):
    serializer_class = PlayerSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = (
            Player.objects.filter(group__memberships__user=self.request.user)
            .annotate(
                matches_played=Count("match_entries", distinct=True),
                goals_for=Count("goals", filter=Q(goals__own_goal=False), distinct=True),
            )
            .select_related("group", "linked_user")
            .distinct()
        )
        group_id = self.request.query_params.get("group")
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        active = self.request.query_params.get("active")
        if active in {"true", "1", "yes"}:
            queryset = queryset.filter(active=True)
        if active in {"false", "0", "no"}:
            queryset = queryset.filter(active=False)
        return queryset

    def perform_update(self, serializer):
        player = self.get_object()
        if not player.group.is_member(self.request.user):
            raise PermissionDenied("No perteneces a este grupo")
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        player = self.get_object()
        if not player.group.is_member(request.user):
            raise PermissionDenied("No perteneces a este grupo")
        player.active = False
        player.save(update_fields=["active"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="stats")
    def stats(self, request, pk=None):
        player = self.get_object()
        return Response(player_stats(player))


class MatchViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = (
            Match.objects.filter(group__memberships__user=self.request.user)
            .select_related("group", "created_by")
            .prefetch_related("participants__player", "goals__player")
            .distinct()
        )
        group_id = self.request.query_params.get("group")
        if group_id:
            queryset = queryset.filter(group_id=group_id)
        player_id = self.request.query_params.get("player")
        if player_id:
            queryset = queryset.filter(participants__player_id=player_id)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return MatchCreateSerializer
        if self.action in {"partial_update", "update"}:
            return MatchUpdateSerializer
        return MatchSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        match = serializer.save()
        response_data = MatchSerializer(match, context={"request": request}).data
        if serializer.goal_warnings:
            response_data["warnings"] = serializer.goal_warnings
        return Response(response_data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        match = self.get_object()
        if not match.can_be_edited():
            raise ValidationError("Los partidos solo se pueden editar durante las primeras 24 horas")
        serializer.save()


class GuestGroupMixin:
    permission_classes = [AllowAny]

    def get_group(self, code: str) -> Group:
        return get_object_or_404(Group, code=code.strip().upper())


class GuestDashboardAPIView(GuestGroupMixin, APIView):
    def get(self, request, code: str):
        return Response(group_dashboard(self.get_group(code)))


class GuestPlayersAPIView(GuestGroupMixin, APIView):
    def get(self, request, code: str):
        group = self.get_group(code)
        queryset = (
            Player.objects.filter(group=group, active=True)
            .annotate(
                matches_played=Count("match_entries", distinct=True),
                goals_for=Count("goals", filter=Q(goals__own_goal=False), distinct=True),
            )
            .order_by("name")
        )
        return Response(PlayerSerializer(queryset, many=True).data)


class GuestMatchesAPIView(GuestGroupMixin, APIView):
    def get(self, request, code: str):
        group = self.get_group(code)
        queryset = (
            Match.objects.filter(group=group)
            .select_related("group", "created_by")
            .prefetch_related("participants__player", "goals__player")
            .order_by("-played_at", "-created_at")
        )
        return Response(MatchSerializer(queryset, many=True).data)
