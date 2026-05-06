from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    GroupViewSet,
    GuestDashboardAPIView,
    GuestMatchesAPIView,
    GuestPlayersAPIView,
    MatchViewSet,
    PlayerViewSet,
)

router = DefaultRouter()
router.register(r"groups", GroupViewSet, basename="group")
router.register(r"players", PlayerViewSet, basename="player")
router.register(r"matches", MatchViewSet, basename="match")

urlpatterns = [
    path("", include(router.urls)),
    path("guest/groups/<str:code>/dashboard/", GuestDashboardAPIView.as_view(), name="guest-dashboard"),
    path("guest/groups/<str:code>/players/", GuestPlayersAPIView.as_view(), name="guest-players"),
    path("guest/groups/<str:code>/matches/", GuestMatchesAPIView.as_view(), name="guest-matches"),
]
