# Migración desde la webapp Django v1

La v1 era monolítica: las views Django usaban el ORM directamente sobre `FriendGroup`, `Player`, `Match`, `Goal`, etc.

La reconstrucción mantiene el enfoque server-rendered de Django pero reemplaza la capa de datos por FastAPI.

## Cambios principales

- eliminados los modelos de dominio del proyecto Django;
- eliminados `access.py` y `services.py` del web frontend;
- agregado `fulbacho/api_client/` como única puerta al dominio;
- autenticación Django reemplazada por usuario de API + access/refresh token;
- sesiones Django conservadas únicamente como almacenamiento server-side de tokens;
- `Player` y `User` quedan independientes y vinculables;
- `MatchParticipant` permite jugadores casuales;
- agregada pantalla para promover casuales o asociarlos a un jugador existente;
- `modality` fue reemplazado por `players_per_team`;
- F5/F6/F8 y otros formatos validan mínimo según el formato;
- los empates son resultados normales;
- el marcador se deriva de `Goal` en la API;
- los goles no asignados se completan como goles anónimos;
- ranking de win rate usa el umbral progresivo acordado;
- el modo invitado también consume únicamente endpoints públicos de FastAPI.

## Qué base usa Django

Django mantiene una base pequeña para `django_session`. Esta base no almacena usuarios, grupos, jugadores, partidos ni estadísticas de Fulbacho.

## Funciones de la v1 no trasladadas

El admin de Django sobre los modelos del dominio deja de existir, porque Django ya no posee esos modelos. La administración funcional se realiza mediante permisos de grupo y endpoints FastAPI.

La importación CSV se rehízo sobre la API. Jugadores usa IDs opcionales para actualizar y partidos exporta/importa un `payload_json` v2 completo, evitando reconstrucciones ambiguas por nombre.
