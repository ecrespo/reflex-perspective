# specs/ — verdad actual de `reflex-perspective`

Nivel de rigor: **spec-anchored**. Las specs viven en el repo, versionadas con el código.
`specs/` describe lo que la librería **hace hoy** (`0.3.0`, Perspective `5.5.1`, Reflex
`0.9.12`; línea base `0.1.0` + los cambios archivados en `changes/_archivo/`). Todo cambio entra como propuesta en [`../changes/`](../changes/) y, al
publicarse la versión que lo implementa, se pliega aquí en el mismo PR.

| Artefacto | Archivo | Qué cubre |
|---|---|---|
| Constitución | [`constitution.md`](constitution.md) | Reglas no negociables del repo |
| PRD | [`prd/reflex-perspective.md`](prd/reflex-perspective.md) | Requisitos (REQ-VIEW, REQ-SRV, REQ-VER) en EARS |
| API | [`api/server-api-v1.md`](api/server-api-v1.md) | Contrato público de `reflex_perspective.server` y del WebSocket |
| Diseño técnico | [`technical/server-architecture.md`](technical/server-architecture.md) | Cómo está hecho el modo servidor y por qué |
| Runbook | [`runbooks/perspective-upgrade.md`](runbooks/perspective-upgrade.md) | Cómo subir de versión Perspective sin romper el protocolo ni el modo sólo lectura |

No hay Data Model: la librería no persiste nada (las tablas viven en memoria en
`perspective-python` o en el navegador).

Línea base reconstruida el 2026-10-03 a partir del código (`custom_components/`), los tests,
el README y los workflows de CI. Donde el código y el README difieren, manda el código.
