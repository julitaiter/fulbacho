from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import FriendGroup, Goal, GroupMember, Match, MatchPlayer, Player, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Fulbacho", {"fields": ("display_name",)}),
    )
    list_display = ("username", "email", "display_name", "is_staff", "is_active")


class GroupMemberInline(admin.TabularInline):
    model = GroupMember
    extra = 0


@admin.register(FriendGroup)
class FriendGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "created_by", "created_at")
    search_fields = ("name", "code")
    readonly_fields = ("code", "created_at", "updated_at")
    inlines = [GroupMemberInline]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "active", "linked_user", "created_at")
    list_filter = ("active", "group")
    search_fields = ("name",)


class MatchPlayerInline(admin.TabularInline):
    model = MatchPlayer
    extra = 0


class GoalInline(admin.TabularInline):
    model = Goal
    extra = 0


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("played_at", "group", "team_a_name", "score_a", "score_b", "team_b_name", "created_by")
    list_filter = ("group", "modality")
    search_fields = ("team_a_name", "team_b_name", "location")
    inlines = [MatchPlayerInline, GoalInline]


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ("match", "player", "team_scored_for", "own_goal", "created_at")
    list_filter = ("own_goal", "team_scored_for")
