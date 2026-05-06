# Migración desde la versión API a webapp

## Eliminado

- `rest_framework`
- `django_filters`
- `corsheaders`
- `serializers.py`
- `ViewSet`
- routers REST
- endpoints `/api/...`
- auth por token/JWT
- documentación de API

## Agregado

- templates HTML
- formularios Django
- views server-rendered
- login/logout clásico
- modo invitado por URL
- CSS propio
- comando seed demo

## Conservado

- Modelo relacional principal.
- Reglas de negocio.
- Códigos de grupo.
- Baja lógica de jugadores.
- Estadísticas y rankings.
- Edición de partidos durante 24 horas.
