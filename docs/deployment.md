# Despliegue en Render

```text
Internet -> Django 0.0.0.0:$PORT -> FastAPI 127.0.0.1:8001 -> Neon/PostgreSQL
```

El Dockerfile de la raíz instala juntos `api/requirements.txt` y
`web/requirements.txt`, sin duplicar las listas de dependencias. Los Dockerfiles
de cada aplicación y Compose siguen siendo el flujo local con servicios separados
y hot reload. El navegador consume únicamente Django; FastAPI no publica su puerto
ni requiere CORS para este flujo. Sus docs quedan accesibles solo dentro del contenedor.

## Bases y variables

Crear dos bases lógicas en Neon, que pueden compartir proyecto/instancia:

- `fulbacho`: `DATABASE_URL`, exclusiva de FastAPI y Alembic; datos del dominio.
- `fulbacho_web`: `WEB_DATABASE_URL`, exclusiva de Django; sesiones y tabla de migraciones.

Usar preferentemente roles separados, cada uno con acceso a su propia base. Copiar
las URLs correspondientes desde Neon, conservando sus parámetros TLS, por ejemplo
`sslmode=require`. Django interpreta directamente `WEB_DATABASE_URL`, sin tomar
`DATABASE_URL` como alternativa. En producción se rechazan SQLite y URLs con el
mismo nombre de base, incluso si tienen usuarios o parámetros diferentes.

La plantilla completa está en [`.env.example`](../.env.example). Cargar en Render:

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

Las variables opcionales `BOOTSTRAP_SUPERUSER_EMAIL`, `BOOTSTRAP_SUPERUSER_PASSWORD`
y `BOOTSTRAP_SUPERUSER_NAME` permiten crear o promover la primera cuenta global.
Su configuración, idempotencia y retiro posterior se explican en [Administración](admin.md#primer-superusuario-en-render).

## Crear el servicio manualmente

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

## Arranque y verificación

`start-render.sh` valida settings, ejecuta `alembic upgrade head`, ejecuta el bootstrap
opcional del superusuario e inicia Uvicorn sin autoreload en loopback y espera su `/health`. Después ejecuta las migraciones
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

## Validación local de producción

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
Las suites Django/FastAPI se ejecutan con los comandos de [Tests](development.md#tests); nunca
ejecutar pytest contra la base de desarrollo o producción. La suite exige sufijo `_test`.

## Documentación relacionada

- [Arquitectura y separación de bases](architecture.md).
- [Desarrollo, tests y registros de validación](development.md).
- [Bootstrap y administración global](admin.md).
