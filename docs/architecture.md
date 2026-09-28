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

La única base que Django puede usar es la propia infraestructura del frontend web, actualmente `django_session`. No es fuente de verdad del dominio.

## Autenticación

FastAPI administra usuarios, passwords, access tokens y refresh tokens. Django guarda los tokens en su sesión server-side y expone un `ApiUser` a los templates. Cuando un access token vence, `ApiClient` intenta renovarlo una vez mediante el refresh token y repite la petición original.

## Responsabilidades

### FastAPI

- autenticación;
- permisos por grupo;
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

## Partidos

La pantalla de Django arma un único payload y lo envía a FastAPI. FastAPI valida el formato, los participantes, los goles y persiste todo en una única transacción.

Los jugadores casuales se representan como `MatchParticipant` sin `player_id`. Desde la web pueden promoverse a un jugador habitual o asociarse a uno existente conservando el historial.
