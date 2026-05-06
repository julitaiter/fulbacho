from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Goal, Group, GroupMember, Match, MatchPlayer, Player, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (("Fulbacho", {"fields": ("display_name",)}),)
    list_display = ["username", "email", "display_name", "is_staff", "created_at"]
    search_fields = ["username", "email", "display_name"]


class GroupMemberInline(admin.TabularInline):
    model = GroupMember
    extra = 0


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "created_by", "created_at"]
    search_fields = ["name", "code"]
    readonly_fields = ["code", "created_at"]
    inlines = [GroupMemberInline]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ["name", "group", "active", "linked_user", "created_at"]
    list_filter = ["active", "group"]
    search_fields = ["name", "group__name"]


class MatchPlayerInline(admin.TabularInline):
    model = MatchPlayer
    extra = 0


class GoalInline(admin.TabularInline):
    model = Goal
    extra = 0


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ["played_at", "group", "team_a_name", "score_a", "score_b", "team_b_name", "created_by"]
    list_filter = ["group", "modality", "played_at"]
    search_fields = ["group__name", "team_a_name", "team_b_name", "location"]
    inlines = [MatchPlayerInline, GoalInline]


@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ["group", "user", "role", "joined_at"]
    list_filter = ["role", "group"]


@admin.register(MatchPlayer)
class MatchPlayerAdmin(admin.ModelAdmin):
    list_display = ["match", "player", "team"]
    list_filter = ["team", "match__group"]


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ["match", "player", "own_goal", "team_scored_for", "created_at"]
    list_filter = ["own_goal", "team_scored_for", "match__group"]
