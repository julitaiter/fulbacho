# Especificación técnica — Fulbacho Django Webapp

## Objetivo

Rehacer Fulbacho como una webapp tradicional, sin API REST ni cliente desacoplado.

El navegador consume HTML renderizado por Django. Las acciones de creación, edición y baja se realizan mediante formularios con protección CSRF y sesiones de Django.

## Arquitectura

```text
[ Navegador ]
     |
     | HTML + forms + CSRF
     v
[ Django Webapp ]
  templates / views / forms
  services / models
     |
     v
[ SQLite o PostgreSQL ]
```

## Módulos

### Autenticación

- Registro de usuario.
- Login con usuario o email.
- Logout.
- Sesión persistente del lado servidor mediante cookies de sesión de Django.

### Grupos

- Crear grupo.
- Código automático de 6 caracteres.
- Creador como admin.
- Unirse a grupo por código.
- Ajustes con código visible y miembros.
- Renombrado solo por admin.

### Invitado

- Entrada desde `/invitado/`.
- Se ingresa código de grupo.
- Redirección a URLs públicas `/invitado/<codigo>/...`.
- No se guarda sesión de invitado.
- Solo lectura: dashboard, partidos y jugadores.
- No aparecen botones de alta, edición o baja.

### Jugadores

- Jugadores pertenecen al grupo, no necesariamente a usuarios.
- Alta por nombre/apodo.
- Baja lógica: `active=False`.
- Historial conservado.
- Perfil con estadísticas.

### Partidos

- Formulario HTML para fecha, modalidad, cancha, equipos, marcador, planteles y goles.
- Validación: mínimo 2 jugadores por equipo.
- Validación: un jugador no puede estar en ambos equipos.
- Validación: los goles cargados no pueden superar el marcador final.
- Edición permitida solo dentro de las primeras 24 horas desde la creación.
- Goles sin asignar permitidos con advertencia visual.

### Estadísticas

- Total de partidos.
- Total de goles de marcador, descontando goles en contra registrados.
- Promedio de goles por partido.
- Partido más goleado.
- Último partido.
- Partidos, victorias, empates y derrotas por jugador.
- Goles a favor, goles en contra, goles netos.
- Racha actual y mejor racha histórica.
- Rankings de goleador, rey del gol en contra, más participativo, mejor porcentaje de victorias y racha activa.

## Decisiones clave

- Se elimina Django REST Framework.
- Se elimina JWT/token auth.
- Se eliminan serializers.
- Se usan `forms.py` y `templates/`.
- `services.py` conserva reglas de negocio para no mezclar validación compleja con HTML views.
- SQLite queda como default local; PostgreSQL puede activarse con `DATABASE_URL`.

## Estructura

```text
backend/
  config/
  fulbacho/
    models.py
    forms.py
    services.py
    views.py
    urls.py
    templates/
    static/
    management/commands/seed_demo.py
```
