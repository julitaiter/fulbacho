# Contrato HTTP

Base: `/api/v1`

## Auth

```text
POST /auth/register
POST /auth/login
POST /auth/refresh
POST /auth/logout
GET  /auth/me
```

Las rutas privadas usan `Authorization: Bearer <access_token>`.

## Grupos

```text
GET    /groups
GET    /groups/overview
POST   /groups
POST   /groups/join
GET    /groups/{group_id}
PATCH  /groups/{group_id}
GET    /groups/{group_id}/members
PATCH  /groups/{group_id}/members/{user_id}
DELETE /groups/{group_id}/members/{user_id}
```

`/groups/overview` agrega cantidad de jugadores activos, partidos y rol del usuario para la pantalla de selección de grupos.

## Jugadores

```text
GET    /groups/{group_id}/players
POST   /groups/{group_id}/players
GET    /groups/{group_id}/players/casuals
POST   /groups/{group_id}/players/promote-casual
GET    /groups/{group_id}/players/{player_id}
PATCH  /groups/{group_id}/players/{player_id}
DELETE /groups/{group_id}/players/{player_id}
POST   /groups/{group_id}/players/{player_id}/attach-casual
```

`DELETE` es baja lógica. `Player` y `User` son entidades independientes; `linked_user_id` es opcional.

## Partidos

```text
GET  /groups/{group_id}/matches
POST /groups/{group_id}/matches
GET  /groups/{group_id}/matches/{match_id}
PUT  /groups/{group_id}/matches/{match_id}
```

El parámetro `players_per_team` define el formato. F5 requiere como mínimo 5 participantes por equipo, F8 requiere 8, etc. Se permiten participantes adicionales.

Los participantes casuales se envían con `name` y sin `player_id`. Los habituales se envían con `player_id`. `ref` identifica al participante dentro del request para asignar goles.

El marcador se materializa mediante registros `Goal`. Cuando el score es mayor que los goles detallados, la API completa la diferencia con goles anónimos.

## Stats

```text
GET /groups/{group_id}/stats/summary
GET /groups/{group_id}/stats/players
GET /groups/{group_id}/stats/players/{player_id}
GET /groups/{group_id}/stats/rankings
```

El ranking de porcentaje de victorias usa el umbral progresivo definido en `docs/models.md`.

## Invitado

No requiere token y es read-only:

```text
GET /guest/{code}
GET /guest/{code}/players
GET /guest/{code}/players/{player_id}
GET /guest/{code}/players/{player_id}/stats
GET /guest/{code}/matches
GET /guest/{code}/matches/{match_id}
GET /guest/{code}/stats/summary
GET /guest/{code}/stats/players
GET /guest/{code}/stats/rankings
```

`GET /guest/{code}/matches` acepta opcionalmente `player_id`.

## Errores

Los errores de dominio tienen forma:

```json
{
  "detail": "Descripción legible",
  "code": "machine_readable_code"
}
```
