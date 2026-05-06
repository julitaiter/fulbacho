# Arquitectura Inicial

## Decisiones

- Frontend: Flutter + `flutter_riverpod` + `go_router`.
- Backend: Supabase.
- Persistencia: PostgreSQL con RLS.
- Estadísticas: calculadas en SQL con views, no materializadas en cliente.

## Estructura del cliente

```text
mobile/lib/
  app/
  core/
    config/
    theme/
  features/
    auth/
    dashboard/
    groups/
    home/
    matches/
    players/
    settings/
```

## Implementación por fases

### Fase 1

- Auth por email.
- Crear grupo.
- Unirse por código.
- CRUD básico de jugadores.

### Fase 2

- Wizard de partido en 4 pasos.
- Alta de goles normales y en contra.
- Historial básico de partidos.

### Fase 3

- Dashboard con `group_stats` y `player_stats`.
- Rankings simples.
- Validaciones de edición dentro de 24 horas.

## Criterios de implementación

- Las reglas críticas se validan en base de datos y también en UI.
- El cliente solo consulta datos del grupo activo.
- Las operaciones de negocio que tocan varias tablas usan RPC (`create_group`, `join_group_by_code`).
