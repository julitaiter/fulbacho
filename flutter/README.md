# Fulbito Stats

Base inicial para construir el MVP definido en `fulbito_stats_spec.docx`.

Este repo arranca con dos piezas:

- `supabase/`: esquema inicial de PostgreSQL, funciones RPC y políticas RLS.
- `mobile/`: esqueleto manual de la app Flutter organizado por features.

## Orden recomendado

1. Crear el proyecto Supabase y ejecutar `supabase/migrations/0001_initial_schema.sql`.
2. Instalar Flutter 3.x en la máquina.
3. Completar los archivos de plataforma dentro de `mobile/` con `flutter create`.
4. Correr `flutter pub get`.
5. Levantar la app con `SUPABASE_URL` y `SUPABASE_ANON_KEY`.

## Comandos sugeridos

```powershell
cd mobile
flutter create .
flutter pub get
flutter run --dart-define=SUPABASE_URL=https://tu-proyecto.supabase.co --dart-define=SUPABASE_ANON_KEY=tu-anon-key
```

## Estado actual

- Modelo de datos inicial alineado con la spec.
- Reglas base de negocio bajadas a SQL.
- RPC listas para crear grupo y unirse por código.
- Navegación y pantallas placeholder del MVP.

## Siguiente tramo de implementación

1. Conectar `AuthGateScreen` con `SupabaseAuth`.
2. Reemplazar placeholders de grupos por repositorios y providers.
3. Implementar wizard de `Nuevo Partido`.
4. Leer estadísticas desde views SQL en el dashboard.
