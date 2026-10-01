# Administración global

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

## Primer superusuario en Render

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

## Bootstrap o promoción manual en desarrollo

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

## Endpoints y pantallas

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

## Documentación relacionada

- [Desarrollo local y tests](development.md).
- [Deploy unificado en Render](deployment.md).
- [Arquitectura y autenticación](architecture.md).
- [Modelo de dominio](models.md).
