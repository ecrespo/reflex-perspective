# Constitución — reflex-perspective

> Versión 1.1 · Ratificada: 2026-10-03 · Última enmienda: 2026-10-03 (Art. 3)
> Ámbito: repositorio `ecrespo/reflex-perspective` (librería, demo y workflows)

## Artículos

### Art. 1 — Calidad de código
EL EQUIPO DEBERÁ mantener en verde el workflow **Quality** (ruff `check` + `format --check`,
chequeo de sintaxis del puente JSX con esbuild, pytest en Python 3.10–3.13, build + `twine
check`, contenido del wheel y `reflex compile` de la demo) antes de cualquier merge a `develop`
o `main`.
*Racional: es una librería publicada en PyPI; un fallo llega directo a los consumidores.*

### Art. 2 — Pruebas trazables
EL EQUIPO DEBERÁ cubrir cada requisito MUST con al menos un test automatizado cuyo docstring
cite el `REQ-…` que verifica. Las pruebas del modo servidor DEBERÁN usar el cliente oficial
de Perspective (`perspective.Client`) para generar los mensajes del protocolo, nunca bytes
escritos a mano, salvo en las pruebas de mensajes malformados o manipulados.
*Racional: el protocolo es binario y cambia entre versiones; sólo el cliente oficial prueba
lo que de verdad manda un navegador.*

### Art. 3 — Versiones de Perspective en bloque
EL SISTEMA DEBERÁ fijar la **misma versión exacta** en `PERSPECTIVE_VERSION`
(`viewer.py`, paquetes npm `@perspective-dev/*`) y en `perspective-python` (extras `server` y
`dev` de `pyproject.toml`). Toda subida DEBERÁ seguir
[`runbooks/perspective-upgrade.md`](runbooks/perspective-upgrade.md). CI DEBERÁ verificar la
igualdad de los pines (REQ-VER-004).
*Racional: cliente y servidor comparten un protocolo protobuf que no tiene compatibilidad
entre versiones; el modo sólo lectura depende de la numeración de ese protocolo.*

### Art. 4 — Compatibilidad hacia atrás
EL SISTEMA DEBERÁ añadir funcionalidad sólo mediante parámetros opcionales cuyo valor por
omisión conserve el comportamiento anterior. Un cambio incompatible DEBERÁ subir la versión
*minor* (mientras sea `0.x`) y documentarse en `CHANGELOG.md` en una sección **Breaking**.
*Racional: los consumidores (p. ej. la consola de CuidaSalud) fijan versiones exactas y
actualizan sin leer el código.*

### Art. 5 — Seguridad: fallar cerrado
EL SISTEMA DEBERÁ rechazar por omisión lo que no sepa clasificar en cualquier control de
acceso (origen, autorización, sólo lectura): un mensaje desconocido, ambiguo o malformado se
trata como prohibido. EL EQUIPO DEBERÁ mantener en verde el workflow **Security** (CodeQL,
Bandit, pip-audit, gitleaks, dependency review).
*Racional: un control de acceso que deja pasar lo desconocido se rompe con la siguiente
versión del protocolo o con el primer mensaje manipulado.*

### Art. 6 — No bloquear Reflex
EL SISTEMA DEBERÁ ejecutar las peticiones al motor de Perspective fuera del lazo de eventos
(executor) y DEBERÁ entregar los mensajes salientes al lazo dueño del socket, aunque las
tablas se actualicen desde otros hilos.
*Racional: un pivote pesado no puede congelar los eventos del resto de la app.*

### Art. 7 — Proceso spec-anchored
EL EQUIPO DEBERÁ tramitar todo cambio de comportamiento como propuesta en `changes/` (proposal
+ delta-spec + tasks) aprobada antes de implementar, y DEBERÁ plegar el delta a `specs/` en el
mismo PR que publica la versión. `version` de `pyproject.toml` y `__version__` DEBERÁN
coincidir (lo verifica CI).
*Racional: si el código cambió y `specs/` no, el cambio no está terminado.*

## Restricciones del stack

- Python ≥ 3.10 para el componente; ≥ 3.11 para el extra `server` (`perspective-python` 5.x
  sólo publica wheels `cp311-abi3`).
- Reflex ≥ 0.9.12. Starlette (el que trae Reflex) para el WebSocket.
- Perspective 5.5.1 (npm `@perspective-dev/*` y `perspective-python`).
- Empaquetado: setuptools ≥ 77, `uv`. CI: GitHub Actions. Publicación: PyPI con Trusted
  Publishing al empujar un tag `vX.Y.Z`.
- Licencia Apache-2.0.

## Enmiendas

| Fecha | Artículo | Cambio | Razón | Aprobado por |
|---|---|---|---|---|
| 2026-10-03 | — | Versión inicial | Línea base SDD del repo | Ernesto Crespo (2026-10-03) |
| 2026-10-03 | Art. 3 | CI verifica la igualdad de los pines de Perspective (REQ-VER-004) | De convención a regla verificada (`changes/_archivo/2026-10-perspective-version-guard/`) | Ernesto Crespo (2026-10-03) |

## Constitution check

Cada propuesta en `changes/` termina con 3-5 líneas: qué artículos aplican y cómo se cumplen,
o qué excepción se pide y por qué.
