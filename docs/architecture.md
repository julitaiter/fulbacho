# Arquitectura de Fulbacho

Fulbacho está dividido en dos aplicaciones independientes:

```text
Navegador
   |
   | HTML + forms + CSRF
   v
Django Web
   |
   | HTTP/JSON + Bearer token
   v
FastAPI
   |
   | SQLAlchemy
   v
PostgreSQL
```

## Regla principal

Django no contiene modelos del dominio de Fulbacho y sus views no acceden a las tablas de usuarios, grupos, jugadores, partidos o goles. Toda lectura o escritura del dominio pasa por FastAPI mediante `web/fulbacho/api_client/`.

La única base que Django puede usar es la propia infraestructura del frontend web:
`django_session` y las migraciones internas (`django_migrations`). No es fuente de
verdad del dominio. `DATABASE_URL` pertenece exclusivamente a FastAPI y Alembic;
Django interpreta únicamente `WEB_DATABASE_URL`, sin recurrir a la URL del dominio.
SQLite se permite en desarrollo. En producción Django requiere PostgreSQL en una
base lógica separada, aunque ambas bases pueden compartir instancia de Neon.

## Autenticación

FastAPI administra usuarios, passwords, access tokens y refresh tokens. Django guarda los tokens en su sesión server-side y expone un `ApiUser` a los templates. Cuando un access token vence, `ApiClient` intenta renovarlo una vez mediante el refresh token y repite la petición original.

Los tokens no se usan para acceder directamente a FastAPI desde el navegador.
`API_SECRET_KEY` firma los tokens de la API; `DJANGO_SECRET_KEY` protege la
infraestructura web. Son claves independientes. La API rechaza usuarios inactivos.
La información de sesión incluye `is_active` e `is_superuser`; las vistas
administrativas consultan `/auth/me` y cada endpoint administrativo comprueba el
permiso actual en FastAPI mediante `require_superuser`.

## Responsabilidades

### FastAPI

- autenticación;
- permisos por grupo;
- autorización y administración de superusuarios globales;
- reglas de negocio;
- transacciones;
- grupos y membresías;
- jugadores habituales y casuales;
- partidos y goles;
- estadísticas y rankings;
- modo invitado;
- persistencia PostgreSQL.

### Django

- routing web;
- forms y CSRF;
- templates HTML;
- adaptación de payloads de formularios a JSON;
- presentación de errores de API;
- sesión web;
- interacción de usuario.

## Organización y ejecución

- `api/`: FastAPI, SQLAlchemy, Alembic y persistencia del dominio en PostgreSQL.
- `web/`: Django server-rendered, formularios, templates y cliente HTTP de la API.
- `docs/`: arquitectura, modelo, desarrollo, despliegue y administración.

En desarrollo Compose ejecuta PostgreSQL, FastAPI y Django como servicios separados,
con hot reload. En producción se usa un único contenedor y Web Service en Render:
Django escucha en `0.0.0.0:$PORT`, FastAPI en `127.0.0.1:8001`, y el cliente web usa
`API_BASE_URL=http://127.0.0.1:8001/api/v1`. El navegador habla con Django; el flujo
principal no depende de CORS. PostgreSQL permanece fuera del contenedor unificado.

La administración sigue `Browser -> Django /admin/ -> FastAPI /api/v1/admin ->
PostgreSQL`. No existe un Django superusuario separado ni un ORM web para modelos
del dominio. Los permisos globales no crean membresías ni cambian roles de grupo.

## Partidos

La pantalla de Django arma un único payload y lo envía a FastAPI. FastAPI valida el formato, los participantes, los goles y persiste todo en una única transacción.

Los jugadores casuales se representan como `MatchParticipant` sin `player_id`. Desde la web pueden promoverse a un jugador habitual o asociarse a uno existente conservando el historial.

## Documentación relacionada

- [Modelo de dominio](models.md).
- [Desarrollo local y tests](development.md).
- [Despliegue unificado](deployment.md).
- [Administración y bootstrap](admin.md).
- [Contrato de la API](../api/docs/api.md).
- [Migración desde v1](migration_from_v1.md).
