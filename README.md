# Fulbacho

Fulbacho es una web para registrar partidos de fútbol entre amigos, gestionar grupos y jugadores y consultar estadísticas e historial.

Esta versión separa claramente frontend web y dominio:

- `api/`: FastAPI + SQLAlchemy + Alembic + PostgreSQL.
- `web/`: Django server-rendered que consume exclusivamente la API para datos de Fulbacho.

## Arquitectura

```text
Browser -> Django -> FastAPI -> PostgreSQL
```

Las views Django no consultan directamente la base de datos del dominio.

## Funcionalidades

- registro, login, logout y refresh de sesión;
- grupos con código de 6 caracteres;
- roles admin/member;
- jugadores habituales vinculables opcionalmente a usuarios;
- jugadores casuales por partido;
- promoción casual -> habitual recuperando participaciones históricas;
- F5/F6/F7/F8/etc. mediante `players_per_team`;
- participantes adicionales permitidos;
- empates;
- goles, goles en contra y goles anónimos;
- edición de partidos durante 24 horas;
- estadísticas y rankings;
- ranking de % de victorias con umbral progresivo;
- modo invitado read-only;
- importación y exportación CSV de jugadores y partidos a través de la API.

## Desarrollo con Docker y hot reload

El archivo `compose.override.yaml`, que Docker Compose carga automáticamente en
desarrollo, monta `./web` y `./api` dentro de sus respectivos contenedores. Django
se ejecuta con `runserver` y FastAPI con Uvicorn `--reload`, por lo que los cambios
en Python reinician el servidor correspondiente y los cambios en templates, CSS y
JavaScript se ven al refrescar el navegador. El volumen `web_sessions` se mantiene
separado del código montado.

En la primera ejecución, o cuando cambien dependencias o un `Dockerfile`:

```bash
cp api/.env.example api/.env  # opcional con compose; compose ya define variables locales
cp web/.env.example web/.env  # opcional con compose

docker compose up --build
```

Para los cambios normales de código posteriores no hace falta reconstruir:

```bash
docker compose up
```

Para iniciar sólo la configuración base (por ejemplo, sin los bind mounts ni el
reload de Uvicorn), se puede indicar el archivo explícitamente:

```bash
docker compose -f docker-compose.yml up --build
```

## Tests

Los tests web se ejecutan dentro del contenedor de Django:

```bash
docker compose exec web python manage.py test
node --test web/fulbacho/tests/js/test_match_form.js
```

La suite de API exige una base aislada cuyo nombre termine en `_test`, porque crea
y elimina su esquema. Para prepararla y ejecutar los tests:

```bash
docker compose exec db createdb -U fulbacho fulbacho_test
docker compose run --rm --no-deps \
  -e TEST_DATABASE_URL=postgresql+psycopg://fulbacho:fulbacho@db:5432/fulbacho_test \
  api sh -lc 'pip install -q -r requirements-dev.txt && pytest'
```

El primer comando se ejecuta una sola vez; si la base ya existe, se puede omitir.

Servicios:

- Web Django: http://127.0.0.1:8000
- Swagger FastAPI: http://127.0.0.1:8001/docs
- PostgreSQL: localhost:5432

## Levantar sin Docker para Python

Primero PostgreSQL/API:

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# ajustar DATABASE_URL si corresponde
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

Luego Django en otra terminal:

```bash
cd web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver 8000
```

## Bases de datos

PostgreSQL detrás de FastAPI es la fuente de verdad de Fulbacho. Django puede usar una pequeña DB propia únicamente para sesiones web (`web.sqlite3` por defecto). En producción puede configurarse con `WEB_DATABASE_URL`.

## Documentación

- `docs/models.md`: modelo de dominio y reglas cerradas.
- `docs/architecture.md`: responsabilidades y flujo entre Django/FastAPI.
- `api/docs/api.md`: contrato de la API.
