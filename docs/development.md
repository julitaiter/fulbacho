# Desarrollo local

Los comandos de este documento se ejecutan desde la raíz del repositorio, salvo
cuando se indica `cd api` o `cd web`. Para Compose se necesita Docker con el plugin
Docker Compose. Para ejecutar Python en el host, la API requiere Python 3.12 o
posterior; el test JavaScript requiere Node.js.

Compose define las variables locales necesarias; no hace falta configurar Neon ni
usar el `.env` de producción de la raíz. No sobrescribir archivos `.env` existentes
al copiar las plantillas. En desarrollo Django mantiene sesiones en SQLite dentro
del volumen `web_sessions`; los datos del dominio están en PostgreSQL local.

## Servicios y puertos

- Web Django: http://127.0.0.1:8000
- Swagger FastAPI: http://127.0.0.1:8001/docs
- PostgreSQL: localhost:5432

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

## Variables locales y operación diaria

- `api/.env.example` y `web/.env.example` son las plantillas para ejecutar cada app
  directamente en el host. Los nombres actuales son `API_SECRET_KEY` / `API_DEBUG`
  y `DJANGO_SECRET_KEY` / `DJANGO_DEBUG`; `SECRET_KEY` / `DEBUG` siguen siendo una
  alternativa en desarrollo.
- En el host, Django usa `API_BASE_URL=http://127.0.0.1:8001/api/v1`; Compose la
  sobrescribe con `http://api:8000/api/v1`. No usar `localhost` para llegar de un
  contenedor separado al otro.
- Compose ejecuta Alembic y las migraciones de sesiones al arrancar. Los cambios
  en dependencias requieren `docker compose up --build`; los cambios habituales
  en código aprovechan los montajes y hot reload.
- El `.env` de la raíz corresponde al [contenedor unificado de producción](deployment.md),
  y no sustituye los `.env` separados al ejecutar las apps directamente en el host.
- Compose no crea superusuarios automáticamente. Para ejecutar el bootstrap
  explícitamente, consultar [Administración](admin.md#bootstrap-o-promoción-manual-en-desarrollo).

```bash
docker compose up -d
docker compose logs -f api web
docker compose exec web python manage.py check
docker compose down
```

`docker compose down` detiene los servicios conservando sus volúmenes. La opción
`--volumes` elimina los datos persistidos y solo debe usarse al querer descartarlos.
Para comprobar la web: `curl -f http://localhost:8000/health/`.


## Registros de validación

Los resultados siguientes corresponden a las validaciones locales realizadas el
1 de octubre de 2026; no son una ejecución nueva de las suites al reorganizar la
documentación.

### Validaciones del superusuario global

Se ejecutaron los tests con PostgreSQL desechable: **44 tests Django y 22 tests
FastAPI aprobados**. La API usó exclusivamente `fulbacho_superuser_test`, con la
protección de sufijo `_test` sin cambios. Los tests Django administrativos usan
sesiones firmadas y prohíben cualquier acceso a DB, comprobando las llamadas HTTP.
Se verificaron acceso anónimo/normal/superusuario, sesiones con permisos antiguos,
promoción y revocación, usuarios inactivos, CSRF, paginación, registro sin escalación
de privilegios y bootstrap sin duplicación, reset de contraseña ni filtración en logs.

También se construyó la imagen unificada y se comprobó por HTTP el login normal,
panel y acciones administrativas con CSRF real contra Gunicorn y FastAPI interno,
además de `/health/` y WhiteNoise. La migración se probó desde `0001` con un usuario
inactivo existente, verificando que conserva su estado y recibe `is_superuser=false`,
incluidos downgrade y nuevo upgrade en una base aislada.

Comandos principales: `python manage.py test`, `python -m pytest`,
`python manage.py check`, `docker build -t fulbacho-superuser-validation .`,
`docker compose -p fulbacho-superuser-dev-validation up --build -d`,
`docker compose config --quiet`, `node --test web/fulbacho/tests/js/test_match_form.js`,
`bash -n start-render.sh` y `git diff --check`. Los tests API se ejecutaron en el
contenedor de validación con `TEST_DATABASE_URL` explícita y dependencias de desarrollo.
El bootstrap repetido informó `unchanged`; Compose no creó usuarios automáticamente.
Se verificó que el supervisor sigue cerrando ambos servidores ante fallos y señales.

### Validaciones del deploy unificado inicial

El 1 de octubre de 2026 se validó con PostgreSQL 16 desechable, sin usar bases de
desarrollo ni de producción. La imagen de prueba se llamó `fulbacho-render-validation`.

```bash
docker build -t fulbacho-render-validation .
docker run --rm --network fulbacho-render-validation-net \
  --env-file /tmp/fulbacho-render-validation.env \
  -e ENVIRONMENT=development -e DJANGO_DEBUG=true -e WEB_DATABASE_URL= \
  -w /app/web fulbacho-render-validation python manage.py test
docker run --rm --network fulbacho-render-validation-net \
  --env-file /tmp/fulbacho-render-validation.env -w /app/api \
  fulbacho-render-validation bash -c \
  'pip install --user -q -r requirements-dev.txt && python -m pytest'
docker exec -w /app/web fulbacho-render-validation-app python manage.py check
node --test web/fulbacho/tests/js/test_match_form.js
docker compose -p fulbacho-dev-validation up --build -d
docker compose config --quiet
bash -n start-render.sh
git diff --check
```

Resultados: 32 tests Django y 10 tests FastAPI aprobados; check Django sin errores;
test JavaScript y build correctos. FastAPI se probó contra `fulbacho_api_test`, distinta
de las bases `fulbacho_validation` y `fulbacho_web_validation` del arranque unificado.
pytest emitió dos avisos de dependencias/transacciones, sin fallos.

También se verificaron por HTTP `/health/`, la portada y los cuatro estáticos CSS/JS,
incluidas las referencias versionadas generadas por WhiteNoise. Se comprobó el registro
y la consulta de grupos desde Django hacia FastAPI por loopback, las tablas de cada
base y la persistencia de sesiones tras reiniciar. FastAPI rechazó conexiones desde
otro contenedor de la misma red.

Las caídas forzadas de Uvicorn y del master Gunicorn hicieron que el contenedor cerrara
el otro servidor y saliera con código 1. `docker kill --signal=SIGTERM` y
`docker kill --signal=SIGINT` cerraron ambos servidores ordenadamente, con códigos
143 y 130. Un arranque con base web inexistente falló en las migraciones Django y
cerró FastAPI. Compose arrancó sus tres servicios con reload y respondió a los
healthchecks; sus contenedores y volúmenes de prueba se eliminaron después.

Estos comandos necesitan preparar la red, el archivo de variables y las bases de
prueba indicadas en [Validación local de producción](deployment.md#validación-local-de-producción); el archivo temporal utilizado no se versiona.
Las validaciones corresponden al entorno local: el deploy en Render queda pendiente
de ejecución manual.

## Documentación relacionada

- [Arquitectura](architecture.md).
- [Despliegue y prueba del contenedor unificado](deployment.md).
- [Administración global](admin.md).
