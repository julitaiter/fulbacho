# Fulbacho v2 — Modelo de datos

## 1. Objetivo

Este documento consolida las decisiones cerradas para el modelo conceptual de datos de Fulbacho v2.

La API se implementará con FastAPI, SQLAlchemy 2, Alembic y PostgreSQL.

Principios del modelo:

- `User` representa una persona registrada en Fulbacho.
- `Player` representa un jugador habitual dentro de un grupo.
- `MatchParticipant` representa a una persona concreta que participó de un partido.
- `User` y `Player` existen en paralelo y pueden vincularse opcionalmente.
- Los jugadores casuales no requieren un `Player` permanente.
- Las estadísticas se derivan de partidos, participantes y goles; no se almacenan como contadores en `Player`.
- El resultado de un partido se deriva de los registros `Goal`.

---

## 2. Diagrama conceptual

```text
User
 │
 ├── created_groups
 │
 └── GroupMember
        │
        ▼
      Group
       │
       ├── Player
       │     └── linked_user_id? ─────► User
       │
       └── Match
            │
            ├── MatchParticipant
            │      └── player_id? ─────► Player
            │
            └── Goal
                   └── participant_id? ─► MatchParticipant
```

Conceptualmente:

```text
User
Persona registrada en Fulbacho
         │
         │ vínculo opcional
         ▼
Player
Jugador habitual de un grupo
         │
         │ participa
         ▼
MatchParticipant
Persona concreta que jugó un partido
```

---

## 3. User

Representa la identidad de una persona dentro de Fulbacho.

```text
users
-----
id UUID PK
email VARCHAR UNIQUE
password_hash VARCHAR
display_name VARCHAR
is_active BOOLEAN
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

### Reglas

- El login se realiza por email.
- No se requiere `username`.
- Un usuario puede pertenecer a múltiples grupos.
- Un usuario puede estar vinculado a distintos `Player` en distintos grupos.
- Dentro de un mismo grupo, un usuario solo puede estar vinculado a un `Player`.

Ejemplo:

```text
User: Julián

Grupo "Los del Jueves"
└── Player: Juli

Grupo "Fútbol oficina"
└── Player: Jota
```

---

## 4. Group

Representa un grupo de amigos que comparte jugadores, partidos y estadísticas.

```text
groups
------
id UUID PK
name VARCHAR
code CHAR(6) UNIQUE
created_by_id UUID FK -> users.id
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

### Reglas

- `code` es un código alfanumérico único de 6 caracteres.
- Se genera automáticamente al crear el grupo.
- El creador del grupo se agrega automáticamente como miembro con rol `admin`.
- El código se utiliza para unirse al grupo y para el acceso invitado de solo lectura.

---

## 5. GroupMember

Representa la pertenencia de un usuario a un grupo.

```text
group_members
-------------
id UUID PK
group_id UUID FK -> groups.id
user_id UUID FK -> users.id
role ENUM('admin', 'member')
joined_at TIMESTAMPTZ
```

### Constraints

```text
UNIQUE(group_id, user_id)
```

### Reglas

- Un usuario puede pertenecer a varios grupos.
- Un usuario no puede tener dos membresías en el mismo grupo.
- Solo los administradores pueden:
  - renombrar el grupo;
  - modificar roles;
  - expulsar miembros.
- Los miembros normales pueden registrar jugadores y partidos.

---

## 6. Player

Representa un jugador habitual dentro de un grupo.

No representa necesariamente a un usuario de Fulbacho.

```text
players
-------
id UUID PK
group_id UUID FK -> groups.id
name VARCHAR
linked_user_id UUID NULL FK -> users.id
active BOOLEAN
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

### Reglas

- Un `Player` pertenece a un único grupo.
- `linked_user_id` es opcional.
- `User` y `Player` son entidades independientes.
- Un jugador puede existir aunque nunca se registre como usuario.
- Un usuario puede estar vinculado a un jugador distinto en cada grupo.
- Dentro del mismo grupo, un usuario no puede estar vinculado a más de un jugador.
- La baja es lógica mediante `active = false`.
- Un jugador inactivo conserva todo su historial y estadísticas.
- Un jugador inactivo no debe aparecer para nuevos partidos.
- El nombre no se utiliza como identidad; el UUID es la identidad real.
- No se impone `UNIQUE(group_id, name)`.

### Constraint recomendado

Se debe garantizar que `linked_user_id`, cuando no sea `NULL`, sea único dentro del grupo:

```text
UNIQUE(group_id, linked_user_id)
```

PostgreSQL permite múltiples `NULL`, por lo que distintos jugadores no vinculados no entran en conflicto.

---

## 7. Match

Representa un partido registrado dentro de un grupo.

```text
matches
-------
id UUID PK
group_id UUID FK -> groups.id
played_at TIMESTAMPTZ
players_per_team INTEGER
location VARCHAR NULL
team_a_name VARCHAR
team_b_name VARCHAR
created_by_id UUID FK -> users.id
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

### `players_per_team`

Reemplaza modalidades cerradas como `futbol5`, `futbol6`, etc.

Ejemplos:

```text
players_per_team = 5  -> F5
players_per_team = 6  -> F6
players_per_team = 8  -> F8
players_per_team = 11 -> F11
```

### Reglas

- Cada equipo debe tener al menos `players_per_team` participantes.
- Se permiten participantes adicionales.
- Ejemplo: en F5 pueden existir 6 o 7 participantes por equipo por suplentes o rotación.
- `players_per_team > 0`.
- Los empates son resultados válidos.
- El partido puede editarse únicamente durante las primeras 24 horas posteriores a su creación.
- La creación y edición del partido deben ser transaccionales.

### Resultado

No se almacenan `score_a` ni `score_b`.

El marcador se deriva de `Goal`:

```text
score_a = COUNT(goals WHERE team_scored_for = 'A')
score_b = COUNT(goals WHERE team_scored_for = 'B')
```

Esto evita inconsistencias entre el marcador y el detalle de goles.

Resultado:

```text
score_a > score_b  -> gana A
score_a < score_b  -> gana B
score_a = score_b  -> empate
```

---

## 8. MatchParticipant

Representa a una persona concreta que participó de un partido.

Este modelo permite diferenciar jugadores habituales de jugadores casuales.

```text
match_participants
------------------
id UUID PK
match_id UUID FK -> matches.id
player_id UUID NULL FK -> players.id
display_name VARCHAR
team ENUM('A', 'B')
created_at TIMESTAMPTZ
```

### Jugador habitual

```text
player_id = UUID
```

Ejemplo:

```json
{
  "player_id": "uuid-juli",
  "display_name": "Juli",
  "team": "A"
}
```

### Jugador casual

```text
player_id = NULL
```

Ejemplo:

```json
{
  "player_id": null,
  "display_name": "Fede amigo de Nico",
  "team": "B"
}
```

### Reglas

- Un `MatchParticipant` pertenece a un único partido.
- Un participante pertenece a un único equipo.
- Un `Player` habitual solo puede aparecer una vez por partido.
- Todo `player_id` utilizado debe pertenecer al mismo grupo del partido.
- Un casual no genera automáticamente un `Player` permanente.
- Los casuales aparecen en el partido y pueden tener goles o goles en contra.
- Los casuales no participan en rankings históricos mientras no estén vinculados a un `Player`.

### Constraint

```text
UNIQUE(match_id, player_id)
```

Como `player_id` puede ser `NULL`, PostgreSQL permite múltiples participantes casuales en un mismo partido.

---

## 9. Goal

Representa un gol del partido.

```text
goals
-----
id UUID PK
match_id UUID FK -> matches.id
participant_id UUID NULL FK -> match_participants.id
own_goal BOOLEAN
team_scored_for ENUM('A', 'B')
created_at TIMESTAMPTZ
```

### Casos

Gol normal:

```text
participant = Juli
own_goal = false
team_scored_for = A
```

Gol en contra:

```text
participant = Juli
own_goal = true
team_scored_for = B
```

Gol sin autor:

```text
participant = NULL
own_goal = false
team_scored_for = A
```

### Reglas

- Un gol debe pertenecer al mismo partido que su participante.
- Un gol normal suma al equipo del participante.
- Un gol en contra suma al equipo contrario.
- Un gol en contra no puede ser anónimo.
- Los goles sin autor están permitidos.
- Todos los goles del marcador deben existir como registros `Goal`.
- Si al crear el partido faltan goleadores detallados, el backend completa automáticamente con goles anónimos.

Ejemplo:

Resultado final:

```text
Equipo A 5 - 3 Equipo B
```

Si para A solo se informan:

```text
Juli
Juli
Nico
```

el backend guarda:

```text
Juli
Juli
Nico
Sin autor
Sin autor
```

De esta forma siempre se cumple:

```text
COUNT(goals A) == score A
COUNT(goals B) == score B
```

---

## 10. Jugadores casuales

Los jugadores casuales representan personas que participaron de un partido sin formar parte habitual del grupo.

Ejemplos:

```text
"Fede amigo de Nico"
"El primo de Tincho"
"Amigo de Juan"
```

No se crea un `Player` automáticamente.

Esto evita ensuciar la lista permanente del grupo con personas que jugaron una sola vez.

---

## 11. Promoción de casual a jugador habitual

El modelo debe permitir convertir posteriormente un jugador casual en habitual.

Ejemplo:

```text
Partido 12 -> "Fede"
Partido 19 -> "Fede amigo de Nico"
Partido 23 -> "Fede"
```

No se debe asumir automáticamente que esas participaciones pertenecen a la misma persona.

La asociación debe ser manual.

### Crear nuevo Player a partir de casuales

Conceptualmente:

```text
crear Player "Fede"
        ↓
seleccionar participaciones históricas
        ↓
asignar player_id del nuevo Player
        ↓
las estadísticas históricas se incorporan automáticamente
```

Endpoint futuro previsto:

```http
POST /api/v1/groups/{group_id}/players/promote-casual
```

Ejemplo:

```json
{
  "name": "Fede",
  "participant_ids": [
    "uuid-participacion-12",
    "uuid-participacion-19",
    "uuid-participacion-23"
  ]
}
```

### Vincular casuales a un Player existente

También debe ser posible vincular participaciones casuales a un jugador habitual ya existente:

```json
{
  "player_id": "uuid-fede",
  "participant_ids": [
    "uuid-participacion-12",
    "uuid-participacion-19"
  ]
}
```

No se realizará matching automático por nombre.

---

## 12. Estadísticas

Las estadísticas no se almacenan como columnas acumuladas en `Player`.

La fuente de verdad es:

```text
Match
MatchParticipant
Goal
```

### Estadísticas de grupo

- total de partidos;
- total de goles;
- promedio de goles por partido;
- partido más goleado;
- último partido.

### Estadísticas de jugador

- partidos jugados;
- victorias;
- derrotas;
- empates;
- porcentaje de victorias;
- goles convertidos;
- goles en contra;
- goles netos;
- racha actual de victorias;
- mejor racha histórica;
- promedio de goles por partido.

### Empates

Los empates:

- son resultados válidos;
- cuentan como partido jugado;
- no cuentan como victoria ni derrota;
- cortan una racha de victorias.

### Rankings

- goleador histórico;
- rey del gol en contra;
- racha activa más larga;
- jugador más participativo;
- mejor porcentaje de victorias.

La elegibilidad para el ranking de porcentaje de victorias depende de la cantidad total de partidos del grupo:

- hasta 5 partidos del grupo: no hay restricción adicional; alcanza con haber jugado al menos un partido;
- de 6 a 15 partidos del grupo: el jugador debe haber disputado al menos `max(floor(total_partidos * 0.25), 2)` partidos;
- más de 15 partidos del grupo: se requieren al menos 5 partidos jugados.

Ejemplos:

```text
Grupo con 5 partidos  -> mínimo 1 partido jugado
Grupo con 6 partidos  -> max(floor(1.5), 2) = 2
Grupo con 8 partidos  -> max(floor(2.0), 2) = 2
Grupo con 10 partidos -> max(floor(2.5), 2) = 2
Grupo con 12 partidos -> max(floor(3.0), 2) = 3
Grupo con 15 partidos -> max(floor(3.75), 2) = 3
Grupo con 16 partidos -> mínimo 5 partidos jugados
```

Los jugadores casuales no aparecen en rankings históricos mientras no estén vinculados a un `Player`.

---

## 13. Invariantes de negocio consolidadas

1. Un usuario puede pertenecer a múltiples grupos.
2. Cada membresía tiene rol `admin` o `member`.
3. Un `Player` pertenece a un único grupo.
4. `User` y `Player` son entidades independientes, pero pueden vincularse opcionalmente.
5. Dentro del mismo grupo, un `User` solo puede estar vinculado a un `Player`.
6. Un `MatchParticipant` pertenece a un único partido.
7. Un `MatchParticipant` puede representar un jugador habitual o un jugador casual.
8. Los casuales no generan automáticamente un `Player`.
9. Los casuales pueden convertirse posteriormente en habituales asociando manualmente participaciones históricas.
10. Un jugador habitual solo puede aparecer una vez en un partido.
11. Un participante solo puede pertenecer a un equipo.
12. Todo `Player` utilizado en un partido debe pertenecer al mismo grupo del partido.
13. Cada equipo debe tener al menos `players_per_team` participantes.
14. Se permiten participantes adicionales por equipo.
15. Los empates están permitidos.
16. Un gol debe pertenecer al mismo partido que su participante.
17. Un gol normal suma al equipo del participante.
18. Un gol en contra suma al equipo contrario.
19. Un gol en contra no puede ser anónimo.
20. Los goles sin autor están permitidos.
21. El resultado se deriva exclusivamente de los registros `Goal`.
22. Todos los goles del marcador deben existir como registros `Goal`.
23. Si faltan goleadores detallados, el backend crea goles anónimos.
24. La creación y edición de un partido deben ser transaccionales.
25. Los partidos pueden editarse únicamente durante las primeras 24 horas posteriores a su creación.
26. La baja de un `Player` es lógica y conserva sus estadísticas históricas.
27. Un `Player` inactivo no aparece para nuevos partidos.
28. Los casuales no aparecen en rankings históricos hasta ser vinculados a un `Player`.
29. La elegibilidad para el ranking de porcentaje de victorias es progresiva: hasta 5 partidos del grupo no hay restricción adicional; de 6 a 15 se exige `max(floor(total_partidos * 0.25), 2)` participaciones; con más de 15 se requieren al menos 5 partidos jugados.
30. Solo admins pueden renombrar grupos, modificar roles o expulsar miembros.
31. Los miembros normales pueden registrar jugadores y partidos.
32. El modo invitado es de solo lectura y utiliza el código del grupo.

---

## 14. Modelos que no existen deliberadamente

No se crean tablas o columnas específicas para estadísticas acumuladas como:

```text
Player.goals_count
Player.matches_played
Player.wins
Player.losses
Player.current_streak
```

Son valores derivados y se calculan desde los datos históricos.

Tampoco se almacenan:

```text
Match.score_a
Match.score_b
```

El resultado se calcula a partir de `Goal.team_scored_for`.

---

## 15. Resumen de relaciones

```text
User 1 ──────── N GroupMember N ──────── 1 Group
User 1 ──────── N Group              (created_by)
User 1 ──────── N Player             (linked_user, opcional)

Group 1 ─────── N Player
Group 1 ─────── N Match

Match 1 ─────── N MatchParticipant
Player 1 ────── N MatchParticipant   (opcional desde participant)

Match 1 ─────── N Goal
MatchParticipant 1 ───── N Goal      (opcional desde goal)
```

---

## 16. Estado

Este modelo conceptual queda cerrado como base para Fulbacho v2.

El próximo paso es traducirlo a:

1. modelos SQLAlchemy 2;
2. constraints e índices PostgreSQL;
3. primera migración Alembic;
4. schemas Pydantic;
5. servicios de dominio;
6. endpoints FastAPI.
