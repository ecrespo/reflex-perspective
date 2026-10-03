# Tasks — Códigos de cierre en el puente del visor (0.3.0)

> Specs de origen: [`proposal.md`](proposal.md), [`delta-spec.md`](delta-spec.md) · Generado: 2026-10-03

Estados: `[ ]` pendiente · `[~]` en curso · `[x] {fecha}` hecha · `[!]` bloqueada (nota).

### [x] 2026-10-03 B-001 · Arnés de pruebas JS
- **Qué**: `tests/js/` con stubs de `react`, `$/env.json` y `$/utils/state`; `tests/test_bridge_js.py`
  empaqueta el puente con `esbuild` (`--alias`, `@perspective-dev/*` externos) y corre `node --test`.
- **Done**: una prueba de `resolveServerUrl` (ya exportada) pasa; sin `node` la prueba se omite.

### [x] 2026-10-03 B-002 · Funciones puras de códigos de cierre
- **Qué**: `closeCodeFromError`, `isPermanentRefusal`, `refusalMessage` exportadas en el puente.
- **REQ**: REQ-VIEW-011
- **Depende de**: B-001
- **Done**: pruebas de `tests/js/bridge.test.mjs` en verde.

### [x] 2026-10-03 B-003 · No reintentar 44xx y `on_disconnect(url, code)`
- **Qué**: `on_error` publica `{url, code}`; mapa de URLs rechazadas que bloquea `scheduleRetry`
  (también en el temporizador ya programado); aviso de consola una vez por URL y código;
  `on_disconnect` con dos firmas en `viewer.py` y `.pyi`.
- **REQ**: REQ-VIEW-011, REQ-VIEW-012
- **Depende de**: B-002
- **Done**: `test_on_disconnect_accepts_url_and_code` en verde; esbuild parsea el puente.

### [x] 2026-10-03 B-004 · Pase en navegador y documentación
- **Qué**: demo: `on_disconnect` muestra el último código en la tarjeta *Access*. Navegador
  headless: 4403 (interruptor cerrado) y 4409 (escritura en sólo lectura) → sin reconexiones
  durante 20 s y un aviso en consola; reinicio del backend (cierre sin 44xx) → reconecta.
  README, CHANGELOG, runbook.
- **REQ**: REQ-VIEW-011, REQ-VIEW-012
- **Depende de**: B-003

## Matriz de trazabilidad

| REQ | Tareas | Verificación |
|---|---|---|
| REQ-VIEW-011 | B-002, B-003, B-004 | `tests/js/bridge.test.mjs`, pase en navegador |
| REQ-VIEW-012 | B-003, B-004 | `test_on_disconnect_accepts_url_and_code`, pase en navegador |

## Registro de ejecución

| Fecha | Tareas | Resultado | Notas |
|---|---|---|---|
| 2026-10-03 | B-001 | hecha | `tests/test_bridge_js.py` empaqueta el puente con esbuild@0.25 (stubs de React y Reflex) y corre `node --test` |
| 2026-10-03 | B-002, B-003 | hecha | 7 pruebas JS + `test_on_disconnect_accepts_url_and_code` rojo → verde; `viewer.pyi` editado a mano (el generador instalado reescribe todo el archivo con otro estilo) |
| 2026-10-03 | B-004 | hecha | Chrome headless sobre la demo en sólo lectura: 4409 → 0 reconexiones en 25 s, un aviso, tarjeta con `4409`; interruptor cerrado → 4403, 1 apertura en 25 s, un aviso; reinicio del backend → reconecta sin aviso. Mensaje real del cliente: `WebSocket closed <código>` (formato confirmado) |
