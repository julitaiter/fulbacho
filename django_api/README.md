# Fulbacho - Backend Django REST

Adaptacion del proyecto Fulbacho/Fulbito Stats para una arquitectura con Python + Django + Django REST Framework.

La especificacion original estaba pensada como app mobile Flutter con Supabase como backend/BaaS. En esta version, Flutter puede seguir siendo el cliente mobile, pero Supabase se reemplaza por una API propia en Django, con PostgreSQL como base de datos recomendada.

## Stack propuesto

| Capa | Tecnologia |
| --- | --- |
| Backend | Python 3.11+ / Django 5.x |
| API | Django REST Framework |
| Autenticacion | Django Auth + JWT con SimpleJWT |
| Base de datos | PostgreSQL recomendado; SQLite como fallback local |
| Admin | Django Admin |
| Deploy | Gunicorn + Whitenoise; compatible con Render, Railway, Fly.io, VPS, Docker, etc. |

## Estructura

```text
fulbacho_django/
├── config/                 # settings, urls, ASGI/WSGI
├── fulbacho/               # dominio principal del MVP
│   ├── models.py           # grupos, jugadores, partidos, goles
│   ├── serializers.py      # contratos JSON para la API
│   ├── views.py            # endpoints autenticados e invitados
│   ├── stats.py            # dashboard, rankings y stats por jugador
│   ├── urls.py             # rutas REST
│   └── admin.py            # administracion Django
├── docs/
│   └── FULBACHO_DJANGO_SPEC.md
├── requirements.txt
├── .env.example
└── manage.py
```

## Instalacion local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py makemigrations fulbacho
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

En Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python manage.py makemigrations fulbacho
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## PostgreSQL

El proyecto usa `DATABASE_URL` si esta variable existe en `.env`:

```env
DATABASE_URL=postgres://postgres:postgres@localhost:5432/fulbacho
```

Si `DATABASE_URL` no existe, Django usa SQLite para levantar el proyecto rapido en desarrollo.

## Endpoints principales

### Autenticacion

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| POST | `/api/auth/token/` | Obtiene access/refresh JWT con usuario y password |
| POST | `/api/auth/token/refresh/` | Renueva access token |

### Grupos

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| GET | `/api/groups/` | Lista grupos del usuario |
| POST | `/api/groups/` | Crea grupo y vuelve admin al creador |
| POST | `/api/groups/join/` | Une al usuario a un grupo por codigo de 6 caracteres |
| GET | `/api/groups/{id}/dashboard/` | Dashboard del grupo autenticado |
| PATCH | `/api/groups/{id}/` | Renombrar grupo; solo admin |

### Jugadores

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| GET | `/api/players/?group={group_id}` | Lista jugadores del grupo |
| POST | `/api/players/` | Crea jugador del grupo |
| PATCH | `/api/players/{id}/` | Edita datos simples del jugador |
| DELETE | `/api/players/{id}/` | Baja logica: marca `active=false` |
| GET | `/api/players/{id}/stats/` | Estadisticas del jugador |

### Partidos

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| GET | `/api/matches/?group={group_id}` | Historial de partidos |
| GET | `/api/matches/?group={group_id}&player={player_id}` | Historial filtrado por jugador |
| POST | `/api/matches/` | Crea partido con participantes y goles |
| PATCH | `/api/matches/{id}/` | Edita datos simples durante las primeras 24 horas |

### Modo invitado, solo lectura

| Metodo | Ruta | Descripcion |
| --- | --- | --- |
| GET | `/api/guest/groups/{code}/dashboard/` | Dashboard por codigo de grupo |
| GET | `/api/guest/groups/{code}/players/` | Jugadores activos por codigo |
| GET | `/api/guest/groups/{code}/matches/` | Partidos por codigo |

## Ejemplo: crear partido

```json
POST /api/matches/
Authorization: Bearer <token>
Content-Type: application/json

{
  "group": "00000000-0000-0000-0000-000000000000",
  "played_at": "2026-03-20T22:00:00-03:00",
  "modality": "futbol5",
  "location": "Cancha del barrio",
  "team_a_name": "Los Cracks",
  "team_b_name": "El Desastre",
  "score_a": 3,
  "score_b": 2,
  "participants": [
    {"player_id": "11111111-1111-1111-1111-111111111111", "team": "A"},
    {"player_id": "22222222-2222-2222-2222-222222222222", "team": "A"},
    {"player_id": "33333333-3333-3333-3333-333333333333", "team": "B"},
    {"player_id": "44444444-4444-4444-4444-444444444444", "team": "B"}
  ],
  "goals": [
    {"player_id": "11111111-1111-1111-1111-111111111111", "own_goal": false, "team_scored_for": "A"},
    {"player_id": "33333333-3333-3333-3333-333333333333", "own_goal": true, "team_scored_for": "A"}
  ]
}
```

La API permite guardar un partido con menos goles detallados que el marcador final y devuelve una advertencia. Rechaza goles detallados que superen el marcador.

## Reglas implementadas

- Un jugador no puede estar dos veces ni en ambos equipos del mismo partido.
- Cada equipo debe tener al menos 2 jugadores.
- Un gol en contra se suma al equipo contrario al del jugador.
- Los goles cargados no pueden superar el resultado final.
- Los partidos solo se pueden editar durante las primeras 24 horas.
- La baja de jugadores es logica, preservando el historial.
- El modo invitado expone solo lectura mediante codigo de grupo.
- Solo admins pueden renombrar un grupo.

## Siguiente tramo recomendado

1. Agregar registro de usuarios por API, ya sea propio o con `dj-rest-auth`/`django-allauth`.
2. Agregar Google OAuth si el cliente Flutter lo necesita.
3. Escribir tests de serializers y permisos para todos los flujos del wizard.
4. Agregar OpenAPI/Swagger con `drf-spectacular`.
5. Conectar el frontend Flutter apuntando a esta API.
