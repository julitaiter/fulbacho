from django.urls import path

from . import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("registro/", views.register, name="register"),
    path("grupos/", views.groups_index, name="groups-index"),
    path("grupos/nuevo/", views.group_create, name="group-create"),
    path("grupos/unirse/", views.group_join, name="group-join"),
    path("grupos/<uuid:group_id>/", views.group_dashboard, name="group-dashboard"),
    path("grupos/<uuid:group_id>/ajustes/", views.group_settings, name="group-settings"),
    path("grupos/<uuid:group_id>/jugadores/", views.players_list, name="players-list"),
    path("grupos/<uuid:group_id>/jugadores/exportar.csv", views.players_export_csv, name="players-export-csv"),
    path("grupos/<uuid:group_id>/jugadores/importar/", views.players_import_csv, name="players-import-csv"),
    path("grupos/<uuid:group_id>/jugadores/nuevo/", views.player_create, name="player-create"),
    path("grupos/<uuid:group_id>/jugadores/<uuid:player_id>/", views.player_detail, name="player-detail"),
    path(
        "grupos/<uuid:group_id>/jugadores/<uuid:player_id>/baja/",
        views.player_deactivate,
        name="player-deactivate",
    ),
    path("grupos/<uuid:group_id>/partidos/", views.matches_list, name="matches-list"),
    path("grupos/<uuid:group_id>/partidos/exportar.csv", views.matches_export_csv, name="matches-export-csv"),
    path("grupos/<uuid:group_id>/partidos/importar/", views.matches_import_csv, name="matches-import-csv"),
    path("grupos/<uuid:group_id>/partidos/nuevo/", views.match_create, name="match-create"),
    path("grupos/<uuid:group_id>/partidos/<uuid:match_id>/", views.match_detail, name="match-detail"),
    path("grupos/<uuid:group_id>/partidos/<uuid:match_id>/editar/", views.match_edit, name="match-edit"),
    path("invitado/", views.guest_code, name="guest-code"),
    path("invitado/<str:code>/", views.guest_dashboard, name="guest-dashboard"),
    path("invitado/<str:code>/jugadores/", views.guest_players, name="guest-players"),
    path("invitado/<str:code>/jugadores/<uuid:player_id>/", views.guest_player_detail, name="guest-player-detail"),
    path("invitado/<str:code>/partidos/", views.guest_matches, name="guest-matches"),
    path("invitado/<str:code>/partidos/<uuid:match_id>/", views.guest_match_detail, name="guest-match-detail"),
]
