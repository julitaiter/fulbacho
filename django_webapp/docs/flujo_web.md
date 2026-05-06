# Flujo web

## Usuario autenticado

```text
Landing
  ├─ Login
  ├─ Registro
  └─ Entrar como invitado

Login / Registro
  ↓
Mis grupos
  ├─ Crear grupo
  ├─ Unirse con código
  └─ Abrir grupo
        ├─ Dashboard
        ├─ Partidos
        │   ├─ Nuevo partido
        │   ├─ Detalle
        │   └─ Editar dentro de 24 hs
        ├─ Jugadores
        │   ├─ Nuevo jugador
        │   ├─ Detalle
        │   └─ Baja lógica
        └─ Ajustes
            ├─ Ver/copiar código
            ├─ Ver miembros
            └─ Renombrar si es admin
```

## Invitado

```text
Landing
  ↓
Ingresar código
  ↓
Dashboard invitado
  ├─ Partidos solo lectura
  └─ Jugadores solo lectura
```

El código viaja en la URL. No se crea usuario ni se guarda sesión de invitado.
