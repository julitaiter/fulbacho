# Fulbacho Django Webapp

Versión **sin API** de Fulbacho: una aplicación web tradicional hecha con **Python + Django**, templates server-side, formularios HTML y sesiones de Django.

Esta variante reemplaza la idea original de Flutter + Supabase por una webapp monolítica. No usa Django REST Framework, no expone endpoints JSON y no necesita frontend mobile separado.

## Qué incluye

- Autenticación con sesiones de Django: registro, login y logout.
- Grupos de amigos con código alfanumérico de 6 caracteres.
- Modo invitado por URL/código, solo lectura y sin sesión persistente.
- Alta, listado, detalle y baja lógica de jugadores.
- Registro y edición de partidos mediante formularios web.
- Asignación de jugadores a Equipo A o Equipo B.
- Carga opcional de goles, incluyendo goles en contra.
- Dashboard server-rendered con estadísticas globales, rankings y tabla por jugador.
- Ajustes de grupo con renombrado solo para administradores.
- Admin de Django para soporte interno.
- Comando `seed_demo` para cargar datos de prueba.

## Stack

- Python 3.11+
- Django 5.x
- SQLite para desarrollo local
- PostgreSQL opcional en producción mediante `DATABASE_URL`
- HTML + CSS propio
- Sin API REST
- Sin DRF
- Sin CORS
- Sin frontend desacoplado

## Instalación rápida

```bash
cd django_webapp/backend

py -m venv .venv
.venv\Scripts\activate # source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env

py manage.py migrate
py manage.py createsuperuser
py manage.py runserver
```

Abrí la web en:

```text
http://127.0.0.1:8000/
```

## Cargar datos demo

```bash
python manage.py seed_demo
```

Crea un usuario de prueba:

```text
usuario: demo
clave: demo12345
```

## Rutas principales

| Ruta | Uso |
|---|---|
| `/` | Landing |
| `/accounts/login/` | Login |
| `/registro/` | Registro |
| `/grupos/` | Mis grupos |
| `/grupos/nuevo/` | Crear grupo |
| `/grupos/unirse/` | Unirse con código |
| `/grupos/<id>/` | Dashboard del grupo |
| `/grupos/<id>/jugadores/` | Jugadores |
| `/grupos/<id>/partidos/` | Partidos |
| `/grupos/<id>/ajustes/` | Ajustes del grupo |
| `/invitado/` | Ingresar como invitado |
| `/invitado/<codigo>/` | Dashboard invitado |
| `/admin/` | Admin Django |

## Diferencias con la versión API

La versión anterior estaba armada como backend para consumir desde un cliente externo. Esta versión concentra todo en Django:

- `views.py` renderiza templates HTML.
- `forms.py` concentra formularios y validaciones de entrada.
- `services.py` mantiene reglas de negocio reutilizables.
- `templates/` define las pantallas.
- `static/` define estilos.
- No hay `serializers.py`, `ViewSet`, routers, JWT, tokens ni endpoints REST.

## Flujo funcional

1. El usuario se registra o inicia sesión.
2. Crea un grupo o se une a uno con código.
3. Carga jugadores del grupo.
4. Registra partidos desde el navegador.
5. Consulta dashboard, historial, jugadores y rankings.
6. Un invitado puede entrar solo con el código para ver información sin modificar nada.

## Producción

Configurá estas variables en `.env` o en el entorno:

```env
SECRET_KEY=una-clave-segura
DEBUG=False
ALLOWED_HOSTS=tu-dominio.com
DATABASE_URL=postgres://usuario:password@host:5432/dbname
CSRF_TRUSTED_ORIGINS=https://tu-dominio.com
```

Después:

```bash
python manage.py collectstatic
python manage.py migrate
```

## Documentación

- `docs/especificacion_django_webapp.md`
- `docs/flujo_web.md`
- `docs/migracion_desde_api.md`
