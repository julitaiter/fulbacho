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

PostgreSQL detrás de FastAPI es la fuente de verdad de Fulbacho. Django usa una DB
propia únicamente para sesiones y migraciones internas. SQLite se permite en
desarrollo; producción exige PostgreSQL con `WEB_DATABASE_URL`.

## Superusuario global y administración

Un **admin de grupo** tiene permisos dentro de su grupo; un **superusuario global**
puede administrar cuentas y consultar todos los grupos y partidos desde `/admin/`.
Los permisos son independientes: una cuenta puede tener ambos, uno o ninguno.
Ser superusuario no agrega membresías ni cambia los roles de los grupos.

Se usa el login normal de Fulbacho. El enlace **Administración** aparece para los
superusuarios. Django consulta `/auth/me` en cada vista administrativa para comprobar
el estado actual, incluso si la sesión conserva un permiso anterior. Toda operación
de dominio se realiza por HTTP hacia FastAPI; la seguridad de cada endpoint se
comprueba en la API contra el usuario activo y su `is_superuser` actual.
No existe un superusuario Django separado, ni se usa `django.contrib.admin` para
usuarios, grupos, jugadores o partidos.

### Primer superusuario en Render

Cargar opcionalmente estas tres variables en el mismo Web Service:

```env
BOOTSTRAP_SUPERUSER_EMAIL=EMAIL_DE_LA_CUENTA
BOOTSTRAP_SUPERUSER_PASSWORD=CONTRASEÑA_INICIAL
BOOTSTRAP_SUPERUSER_NAME=NOMBRE_VISIBLE
```

No versionar valores reales. Se requieren las tres para ejecutar el bootstrap;
si falta alguna, se omite correctamente sin crear ni modificar cuentas. Se validan
email, nombre y contraseña con las mismas reglas de registro (8 a 128 caracteres
para la contraseña), y se utiliza el mismo hash Argon2 que en la autenticación.
La contraseña no se imprime en los logs.

El arranque ejecuta Alembic y luego `api/scripts/bootstrap_superuser.py`, antes de
Uvicorn. Si la cuenta no existe, la crea activa y superusuario. Si ya existe, la
promueve sin cambiar su contraseña, nombre ni estado activo. Si ya es superusuario,
no la modifica ni la duplica. El bootstrap es idempotente y serializa ejecuciones
concurrentes para el mismo email. No se ejecuta durante el build.

Después del primer arranque correcto, comprobar el mensaje
`Superuser bootstrap: created.` o `promoted.`, iniciar sesión normalmente y visitar
`/admin/`. Retirar las tres variables de Render cuando ya no sean necesarias; si
se dejan configuradas, una cuenta que haya perdido `is_superuser` volverá a ser
promovida en el siguiente arranque. No se resetean contraseñas en los deploys.

### Bootstrap o promoción manual en desarrollo

Compose no ejecuta automáticamente el bootstrap. Para ejecutarlo explícitamente,
cargar las tres variables en `api/.env` y usar:

```bash
docker compose exec api python scripts/bootstrap_superuser.py
```

El override de desarrollo monta `api/`, por lo que el script lee ese `.env`. Con
Python directo en el host, activar el entorno virtual de la API y ejecutar:

```bash
cd api
python scripts/bootstrap_superuser.py
```

El script también acepta variables de entorno y les da prioridad sobre `api/.env`.
Para promover manualmente una cuenta existente, usar su email con las tres variables
y ejecutar el mismo script del lado FastAPI. La contraseña suministrada se valida
pero no reemplaza la existente. Una cuenta existente inactiva seguirá inactiva;
otro superusuario activo puede reactivarla desde el detalle de usuario.
También se puede otorgar o quitar el permiso desde `/admin/users/` con una sesión
de superusuario. Las acciones sobre la propia cuenta actualizan la sesión: quitar
el permiso redirige a Mis grupos; desactivarse cierra la sesión.

### Endpoints y pantallas

Todos los endpoints siguientes usan `require_superuser` (401 sin autenticación o
con usuario inactivo; 403 para usuarios activos sin permiso global):

| Método | Ruta bajo `/api/v1/admin` | Función |
| --- | --- | --- |
| GET | `/users` | Listar usuarios |
| GET | `/users/{user_id}` | Detalle sin hash de contraseña |
| PATCH | `/users/{user_id}` | Cambiar `is_active` y/o `is_superuser` |
| GET | `/groups` | Listar todos los grupos |
| GET | `/groups/{group_id}` | Detalle de grupo |
| GET | `/groups/{group_id}/members` | Consultar miembros y roles |
| GET | `/matches` | Listar todos los partidos |
| GET | `/matches/{match_id}` | Detalle de partido, participantes y goles |

Los listados aceptan `offset` (desde 0) y `limit` (1 a 100, por defecto 50), con
orden estable. PATCH acepta únicamente los dos flags como booleanos JSON; no permite
modificar credenciales ni otros campos. No hay acciones de eliminación.

Django ofrece dashboard `/admin/`, listados y detalles en `/admin/users/`,
`/admin/groups/` y `/admin/matches/`, además de las acciones POST de usuarios con
protección CSRF. Las páginas mantienen las plantillas y estilos actuales.
`/auth/me` y las respuestas de login, registro y refresh ahora incluyen
`is_superuser` junto con `is_active`.

La migración Alembic `0002_global_superuser.py` agrega `is_superuser=false` a todas
las cuentas existentes y establece el default SQL de `is_active=true`, sin cambiar
su estado actual. No hay migraciones Django de dominio.

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

## Producción: un único Web Service en Render

```text
Internet -> Django 0.0.0.0:$PORT -> FastAPI 127.0.0.1:8001 -> Neon/PostgreSQL
```

El Dockerfile de la raíz instala juntos `api/requirements.txt` y
`web/requirements.txt`, sin duplicar las listas de dependencias. Los Dockerfiles
de cada aplicación y Compose siguen siendo el flujo local con servicios separados
y hot reload. El navegador consume únicamente Django; FastAPI no publica su puerto
ni requiere CORS para este flujo. Sus docs quedan accesibles solo dentro del contenedor.

### Bases y variables

Crear dos bases lógicas en Neon, que pueden compartir proyecto/instancia:

- `fulbacho`: `DATABASE_URL`, exclusiva de FastAPI y Alembic; datos del dominio.
- `fulbacho_web`: `WEB_DATABASE_URL`, exclusiva de Django; sesiones y tabla de migraciones.

Usar preferentemente roles separados, cada uno con acceso a su propia base. Copiar
las URLs correspondientes desde Neon, conservando sus parámetros TLS, por ejemplo
`sslmode=require`. Django interpreta directamente `WEB_DATABASE_URL`, sin tomar
`DATABASE_URL` como alternativa. En producción se rechazan SQLite y URLs con el
mismo nombre de base, incluso si tienen usuarios o parámetros diferentes.

La plantilla completa está en [`.env.example`](.env.example). Cargar en Render:

| Variable | Valor |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `API_SECRET_KEY` | Secreto aleatorio independiente |
| `API_DEBUG` | `false` |
| `DATABASE_URL` | `postgresql+psycopg://USUARIO:CLAVE@HOST/fulbacho?sslmode=require` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` |
| `DJANGO_SECRET_KEY` | Otro secreto aleatorio, distinto del de API |
| `DJANGO_DEBUG` | `false` |
| `ALLOWED_HOSTS` | Host asignado por Render, sin esquema ni barra final |
| `CSRF_TRUSTED_ORIGINS` | `https://` seguido del host asignado por Render |
| `API_BASE_URL` | `http://127.0.0.1:8001/api/v1` |
| `API_TIMEOUT_SECONDS` | `10` |
| `WEB_DATABASE_URL` | `postgresql://USUARIO:CLAVE@HOST/fulbacho_web?sslmode=require` |
| `CORS_ORIGINS` | Vacío, o dejar sin definir |

`ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` aceptan listas separadas por comas; no hay
dominio de producción predeterminado. No usar comodines. Render proporciona `PORT`;
el script usa `10000` como valor de reserva. Generar cada secreto por separado,
por ejemplo con `python -c 'import secrets; print(secrets.token_urlsafe(48))'`.
Los `.env` no se versionan ni se incluyen en la imagen. Los archivos locales
`api/.env` y `web/.env` siguen funcionando, con los nuevos nombres o con los nombres
antiguos `SECRET_KEY` / `DEBUG` como alternativa solo para desarrollo.

### Crear el servicio manualmente

1. Subir estos cambios a GitHub y elegir **New > Web Service** en Render.
2. Conectar el repositorio y seleccionar la rama a desplegar.
3. Language/runtime: **Docker**. Root Directory: vacío (raíz del repositorio).
   Dockerfile Path: `./Dockerfile`; Docker build context: raíz (`.`).
4. Start Command / Docker Command: dejar vacío para usar el `CMD` de la imagen.
   Si se indica explícitamente, usar `/app/start-render.sh`.
5. Health Check Path: `/health/`.
6. Cargar las variables anteriores con las URLs de las dos bases y los dos secretos.
   Consultar el hostname asignado al servicio y cargarlo en las variables de host
   y CSRF antes de esperar un deploy saludable; si Render lo muestra después de
   crear el servicio, actualizar esas variables y volver a desplegar.
7. Crear/desplegar únicamente este Web Service. No usar el antiguo descriptor de
   API independiente (se retiró `api/render.yaml`).

Estos campos corresponden a la documentación oficial de
[Docker en Render](https://render.com/docs/docker) y
[health checks](https://render.com/docs/health-checks).

### Arranque y verificación

`start-render.sh` valida settings, ejecuta `alembic upgrade head`, ejecuta el bootstrap
opcional del superusuario e inicia Uvicorn
sin autoreload en loopback y espera su `/health`. Después ejecuta las migraciones
Django, `collectstatic` e inicia Gunicorn en `0.0.0.0:$PORT`. WhiteNoise sirve los
estáticos recogidos con nombres versionados desde `/static/css/` y `/static/js/`,
manteniendo `web/fulbacho/static/css/` y `web/fulbacho/static/js/` como fuentes.

El supervisor vigila ambos servidores, también durante las migraciones Django.
Si cualquiera termina inesperadamente, detiene el otro y sale con error. SIGTERM
y SIGINT se transmiten a sus grupos de procesos, incluidos los workers, con hasta
25 segundos de cierre ordenado y terminación forzada posterior si fuera necesaria.
Un fallo de migraciones o `collectstatic` también detiene el contenedor.

Tras desplegar, reemplazar `HOST_ASIGNADO` en:

```bash
curl -f https://HOST_ASIGNADO/health/
curl -f https://HOST_ASIGNADO/static/css/app.css
curl -f https://HOST_ASIGNADO/static/js/match-form.js
```

`/health/` comprueba que Django responde (HTTP 200); no realiza consultas de dominio
ni garantiza por sí solo disponibilidad de Neon. Verificar además registro/login,
creación de un grupo y persistencia de sesión tras reiniciar el servicio. En DevTools,
las solicitudes del navegador deben apuntar al host Django. Los logs deben mostrar
Uvicorn en `127.0.0.1:8001` y Gunicorn en el puerto público. FastAPI y PostgreSQL no
se exponen desde este contenedor.

### Validación local de producción

Construir con `docker build -t fulbacho-render .`. Para el arranque usar un archivo
local ignorado por Git, por ejemplo `/tmp/fulbacho-render.env`, con las variables
anteriores y dos bases PostgreSQL **de prueba separadas**. Si PostgreSQL está en
otro contenedor, usar una red Docker común y su nombre DNS en ambas URLs. Para
PostgreSQL local sin TLS se pueden omitir los parámetros TLS; en Neon conservarlos.
En la prueba local usar `ALLOWED_HOSTS=localhost,127.0.0.1` y
`CSRF_TRUSTED_ORIGINS=http://localhost:10000,http://127.0.0.1:10000`.
Para esta comprobación local por HTTP, definir `ENVIRONMENT=development` en el
archivo de variables, manteniendo `API_DEBUG=false` y `DJANGO_DEBUG=false` para
usar los servidores y estáticos de producción. Esto permite los orígenes HTTP
locales sin modificar la validación de producción, que exige HTTPS. En Render
mantener `ENVIRONMENT=production` y `CSRF_TRUSTED_ORIGINS=https://HOST_ASIGNADO`.
Para probar también la validación de producción localmente, usar un proxy HTTPS
y configurar el origen HTTPS correspondiente.

```bash
docker run --rm --name fulbacho-render --network RED_DE_PRUEBA \
  --env-file /tmp/fulbacho-render.env -p 10000:10000 fulbacho-render
curl -f http://localhost:10000/health/
curl -f http://localhost:10000/static/css/app.css
curl -f http://localhost:10000/static/js/match-form.js
docker exec -w /app/web fulbacho-render python manage.py check
docker exec -w /app/web fulbacho-render python manage.py shell -c \
  'from fulbacho.api_client.client import ApiClient; from fulbacho.api_client.exceptions import ApiError
try:
    ApiClient().get("/guest/INVALID", auth=False)
except ApiError as error:
    assert error.status_code == 404, error
    print("Django -> FastAPI: HTTP 404 esperado para un código inexistente")'
```

El último comando permite comprobar el transporte usando el cliente real de Django:
para un código inexistente, es esperable un HTTP 404. Para comprobar
un flujo exitoso, usar un código de grupo existente en la base de prueba.
Las suites Django/FastAPI se ejecutan con los comandos de la sección Tests; nunca
ejecutar pytest contra la base de desarrollo o producción. La suite exige sufijo `_test`.

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
prueba indicadas en la sección anterior; el archivo temporal utilizado no se versiona.
Las validaciones corresponden al entorno local: el deploy en Render queda pendiente
de ejecución manual.

## Documentación

- `docs/models.md`: modelo de dominio y reglas cerradas.
- `docs/architecture.md`: responsabilidades y flujo entre Django/FastAPI.
- `api/docs/api.md`: contrato de la API.
