from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import FriendGroup, GroupMember, GroupRole


def groups_for_user(user):
    return FriendGroup.objects.filter(memberships__user=user).distinct()


def get_group_for_user(user, group_id):
    return get_object_or_404(groups_for_user(user), id=group_id)


def is_group_member(user, group: FriendGroup) -> bool:
    if not user.is_authenticated:
        return False
    return GroupMember.objects.filter(group=group, user=user).exists()


def is_group_admin(user, group: FriendGroup) -> bool:
    if not user.is_authenticated:
        return False
    return GroupMember.objects.filter(group=group, user=user, role=GroupRole.ADMIN).exists()


def ensure_group_member(user, group: FriendGroup) -> None:
    if not is_group_member(user, group):
        raise PermissionDenied("No pertenecés a este grupo.")


def ensure_group_admin(user, group: FriendGroup) -> None:
    if not is_group_admin(user, group):
        raise PermissionDenied("Solo un admin puede hacer esta acción.")
