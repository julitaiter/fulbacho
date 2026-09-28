# Arquitectura

## Capas

```text
HTTP / FastAPI router
        |
        v
Domain service
        |
        v
SQLAlchemy Session
        |
        v
PostgreSQL
```

Los routers se limitan a autenticación HTTP, parámetros y schemas. Las reglas de negocio viven en `service.py`.

## Módulos

- `auth`: usuarios, passwords, access tokens y refresh tokens rotativos.
- `groups`: grupos, códigos, membresías, roles y permisos.
- `players`: jugadores habituales, baja lógica, vínculo con usuarios y promoción de casuales.
- `matches`: partidos, participantes habituales/casuales, goles y edición transaccional.
- `stats`: estadísticas y rankings derivados; no persiste contadores.
- `guest`: proyección pública read-only mediante código de grupo.

## Fuente de verdad

El resultado no se persiste en `Match`. Se deriva de `Goal.team_scored_for`. El request de alta/edición sí recibe `score` por equipo para poder completar automáticamente goles anónimos cuando no se conocen todos los autores.

## Casual -> habitual

`MatchParticipant.player_id` es nullable. Una participación casual tiene `player_id=NULL`. Al promoverla o asociarla a un `Player`, las estadísticas históricas se incorporan automáticamente porque todos los cálculos parten de `MatchParticipant` y `Goal`.

## Seguridad

- Passwords con Argon2 mediante `pwdlib`.
- Access token JWT corto.
- Refresh token aleatorio persistido únicamente como SHA-256.
- Refresh rotation: cada refresh revoca el anterior y emite uno nuevo.
- Logout revoca el refresh token.
- Todas las operaciones privadas validan membresía del grupo.
- Operaciones administrativas exigen rol `admin`.
