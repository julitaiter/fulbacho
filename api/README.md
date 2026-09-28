# Fulbacho API v2

API REST para Fulbacho construida con FastAPI, SQLAlchemy 2, Alembic y PostgreSQL.

El modelo implementa grupos compartidos, jugadores habituales y casuales, partidos con formato F5/F6/F8/etc., goles, goles en contra, promoción de casuales a jugadores habituales, estadísticas, rankings y acceso invitado.

## Stack

- FastAPI
- SQLAlchemy 2
- Alembic
- PostgreSQL
- Pydantic v2 / pydantic-settings
- JWT access + refresh tokens
- pwdlib (Argon2)
- pytest

## Desarrollo local

### 1. Crear entorno

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

### 2. Levantar PostgreSQL

```bash
docker compose up -d db
```

### 3. Migraciones

```bash
py -m alembic upgrade head
```

### 4. Ejecutar

```bash
py -m uvicorn app.main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

OpenAPI:

```text
http://127.0.0.1:8000/openapi.json
```

## Tests

```bash
py -m pytest
```

Los tests usan una base PostgreSQL separada indicada por `TEST_DATABASE_URL`. Por seguridad no usan SQLite, para mantener el mismo comportamiento de constraints que producción.

## Endpoints principales

```text
/api/v1/auth/*
/api/v1/groups/*
/api/v1/groups/{group_id}/players/*
/api/v1/groups/{group_id}/matches/*
/api/v1/groups/{group_id}/stats/*
/api/v1/guest/{code}/*
```

## Decisiones de dominio

- `User` y `Player` son entidades independientes y se pueden vincular.
- `MatchParticipant` representa a quien jugó realmente un partido.
- Un participante sin `player_id` es casual.
- Un casual puede promocionarse después a jugador habitual y recuperar sus estadísticas históricas.
- El marcador se deriva exclusivamente de `Goal`.
- Todos los goles del resultado tienen registro; los faltantes se crean como anónimos.
- Los empates existen y cortan rachas de victorias.
- El mínimo por equipo depende de `players_per_team`.
- Los partidos se editan solo dentro de las primeras 24 horas desde su creación.
- Los casuales no aparecen en rankings históricos hasta ser vinculados a un `Player`.
- Ranking de porcentaje de victorias:
  - hasta 5 partidos del grupo: mínimo 1 partido jugado;
  - de 6 a 15: `max(floor(total * 0.25), 2)`;
  - más de 15: mínimo 5 partidos jugados.
