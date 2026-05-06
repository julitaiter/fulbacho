# Fulbacho - Especificacion adaptada a Django

## 1. Objetivo

Fulbacho registra estadisticas de partidos informales de futbol 5/6 entre amigos. Esta adaptacion mantiene el producto original, pero reemplaza Supabase por un backend propio en Django REST Framework.

El cliente mobile Flutter puede seguir existiendo. La diferencia es que ahora consume una API HTTP/JSON propia.

## 2. Stack adaptado

| Capa | Original | Adaptado a Django |
| --- | --- | --- |
| Frontend | Flutter 3.x | Flutter 3.x o cualquier cliente HTTP |
| Backend | Supabase | Django + Django REST Framework |
| Auth | Supabase Auth | Django Auth + JWT SimpleJWT |
| Base de datos | PostgreSQL via Supabase | PostgreSQL propio; SQLite fallback dev |
| Seguridad de datos | Supabase RLS | Querysets filtrados + permisos DRF |
| Dashboard | SQL/views en Supabase | Servicios Python en `fulbacho/stats.py`; migrable a views SQL |
| Admin | No aplica | Django Admin |

## 3. Arquitectura

```text
[ Flutter / Web / Cliente ]
          |
          | HTTP JSON + JWT
          v
[ Django REST Framework ]
  - ViewSets / APIViews
  - Serializers
  - Permissions / querysets por usuario
  - Servicios de estadisticas
          |
          v
[ PostgreSQL ]
  - profiles/users
  - groups
  - group_members
  - players
  - matches
  - match_players
  - goals
```

## 4. Modulos funcionales

### 4.1 Autenticacion

- Login JWT: `/api/auth/token/`.
- Refresh JWT: `/api/auth/token/refresh/`.
- Registro de usuarios: pendiente para implementar como endpoint propio o con `dj-rest-auth`.
- Google OAuth: pendiente, recomendado con `django-allauth`.
- Modo invitado: no crea sesion; usa rutas publicas por codigo de grupo.

### 4.2 Grupos

- Un usuario puede crear multiples grupos.
- Al crear un grupo se genera un codigo alfanumerico unico de 6 caracteres.
- El creador queda como admin.
- Un usuario puede unirse por codigo con `/api/groups/join/`.
- Solo admin puede renombrar grupo.

### 4.3 Jugadores

Los jugadores pertenecen al grupo y no necesitan usuario. Opcionalmente se pueden vincular a un usuario de Django.

- Alta de jugador: nombre + grupo.
- Baja logica: `active=false`.
- Mini-stats: partidos jugados y goles.
- Estadisticas detalladas: `/api/players/{id}/stats/`.

### 4.4 Registro de partidos

Se implementa como POST unico a `/api/matches/`, pensado para recibir el resultado final del wizard mobile.

Flujo del cliente:

1. Crear partido: fecha, modalidad, lugar, nombres de equipos.
2. Enviar participantes con `player_id` y equipo `A` o `B`.
3. Enviar marcador y goles detallados opcionales.
4. Confirmar y guardar.

Validaciones del backend:

- El usuario debe ser miembro del grupo.
- Cada equipo necesita al menos 2 jugadores.
- Un jugador no puede repetirse.
- Cada jugador debe pertenecer al grupo y estar activo.
- Un gol a favor se suma al equipo del jugador.
- Un gol en contra se suma al equipo contrario.
- Los goles detallados no pueden superar el marcador final.
- Si faltan autores de goles, se guarda y se devuelve advertencia.
- Edicion simple permitida solo durante 24 horas.

## 5. Modelo de datos Django

### profiles

Representado por el modelo custom `User`, que extiende `AbstractUser` y usa UUID como clave primaria.

| Campo | Tipo | Descripcion |
| --- | --- | --- |
| id | UUID | Identificador del usuario |
| username | text | Usuario Django |
| email | email unique | Email |
| display_name | text | Nombre visible |
| created_at | datetime | Fecha de registro |

### groups

| Campo | Tipo | Descripcion |
| --- | --- | --- |
| id | UUID | Identificador del grupo |
| name | text | Nombre del grupo |
| code | char(6) unique | Codigo publico de invitacion/invitado |
| created_by | FK User | Creador/admin inicial |
| created_at | datetime | Fecha de creacion |

### group_members

| Campo | Tipo | Descripcion |
| --- | --- | --- |
| id | UUID | Identificador |
| group | FK Group | Grupo |
| user | FK User | Usuario |
| role | admin/member | Rol |
| joined_at | datetime | Fecha de ingreso |

### players

| Campo | Tipo | Descripcion |
| --- | --- | --- |
| id | UUID | Identificador |
| group | FK Group | Grupo del jugador |
| name | text | Nombre o apodo |
| linked_user | FK User nullable | Usuario vinculado opcional |
| active | bool | Baja logica |
| created_at | datetime | Fecha de alta |

### matches

| Campo | Tipo | Descripcion |
| --- | --- | --- |
| id | UUID | Identificador |
| group | FK Group | Grupo |
| played_at | datetime | Fecha/hora del partido |
| modality | futbol5/futbol6 | Modalidad |
| location | text nullable | Cancha/lugar |
| team_a_name | text | Nombre equipo A |
| team_b_name | text | Nombre equipo B |
| score_a | int | Goles equipo A |
| score_b | int | Goles equipo B |
| created_by | FK User | Usuario que registro |
| created_at | datetime | Fecha de registro |

### match_players

| Campo | Tipo | Descripcion |
| --- | --- | --- |
| id | UUID | Identificador |
| match | FK Match | Partido |
| player | FK Player | Jugador |
| team | A/B | Equipo |

### goals

| Campo | Tipo | Descripcion |
| --- | --- | --- |
| id | UUID | Identificador |
| match | FK Match | Partido |
| player | FK Player nullable | Autor; puede ser anonimo |
| own_goal | bool | Gol en contra |
| team_scored_for | A/B | Equipo al que se suma el gol |
| created_at | datetime | Fecha de carga |

## 6. Seguridad y permisos

| Caso | Regla |
| --- | --- |
| Usuario autenticado lista grupos | Solo sus grupos |
| Usuario crea grupo | Creador queda admin |
| Usuario se une a grupo | Debe conocer codigo |
| Usuario lista jugadores/partidos | Solo grupos donde es miembro |
| Usuario crea jugador/partido | Solo si pertenece al grupo |
| Renombrar grupo | Solo admin |
| Invitado | Solo rutas `/api/guest/...`, sin escritura |

## 7. Dashboard

`fulbacho/stats.py` calcula:

- Total de partidos.
- Goles totales a favor, sin contar goles en contra.
- Promedio de goles por partido.
- Partido mas goleado.
- Ultimo partido.
- Estadisticas por jugador:
  - partidos jugados,
  - victorias/derrotas/empates,
  - porcentaje de victorias,
  - goles a favor,
  - goles en contra,
  - goles netos,
  - racha actual,
  - mejor racha historica,
  - promedio de goles por partido.
- Rankings:
  - goleadores,
  - rey del gol en contra,
  - racha activa,
  - jugador mas participativo,
  - porcentaje de victorias con minimo 5 partidos.

## 8. Contrato recomendado para Flutter

- Guardar `accessToken` y `refreshToken` de SimpleJWT.
- En cada request autenticada, enviar:

```http
Authorization: Bearer <accessToken>
```

- Si la API responde 401, intentar refresh con `/api/auth/token/refresh/`.
- En modo invitado, no guardar sesion; guardar solo en memoria el codigo ingresado y consultar rutas `/api/guest/groups/{code}/...`.

## 9. Roadmap adaptado

| Fase | Entregables Django |
| --- | --- |
| MVP | Modelos, admin, JWT, grupos, jugadores, partidos, dashboard basico |
| v1.1 | Registro de usuarios, OAuth Google, tests completos, edicion avanzada de partidos |
| v1.2 | OpenAPI, filtros avanzados, cache de dashboard, notificaciones push desde backend |
| v2.0 | Torneos, chat, modo arbitro en vivo, realtime con WebSockets/Django Channels |
