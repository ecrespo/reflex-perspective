# Delta — Códigos de cierre en el puente del visor (0.3.0)

> Propuesta: [`proposal.md`](proposal.md) · Tareas: [`tasks.md`](tasks.md)

## ADDED

### specs/prd/reflex-perspective.md → §4.1 Visor

- **REQ-VIEW-011** (no deseado): SI el WebSocket de un visor en modo servidor se cierra con un
  código entre 4400 y 4499 distinto de 4429, ENTONCES EL SISTEMA NO DEBERÁ reintentar la
  conexión a esa URL hasta que se recargue la página y DEBERÁ escribir en la consola del
  navegador un aviso con el código y su causa probable.
- **REQ-VIEW-012** (evento): CUANDO se pierda la conexión de un visor en modo servidor, EL
  SISTEMA DEBERÁ emitir `on_disconnect` con la URL y el código de cierre (`None` si no se
  conoce); un handler de un solo argumento DEBERÁ seguir recibiendo la URL.

### Puente (`perspective_viewer.jsx`) → funciones exportadas

| Función | Comportamiento |
|---|---|
| `closeCodeFromError(error)` | Código de `WebSocket closed <código>` en el mensaje (o texto) del error; `null` si no aparece |
| `isPermanentRefusal(code)` | `true` para 4400–4499 salvo 4429 |
| `refusalMessage(code, url)` | Texto del aviso de consola (4401, 4403, 4409, genérico) |

### specs/runbooks/perspective-upgrade.md → §2

- Comprobar en `rust/perspective-client/../src/ts/websocket.ts` del tag nuevo que `onclose`
  sigue llamando `handle_error("WebSocket closed " + event.code, …)`; si cambia, actualizar
  `closeCodeFromError` y sus pruebas.

### tests

- `tests/js/bridge.test.mjs` (node:test), lanzado por `tests/test_bridge_js.py`:
  `closeCodeFromError` con `Error`, texto y valores sin código; `isPermanentRefusal` en los
  bordes 4399/4400/4429/4499/4500; `refusalMessage` nombra el código y, para 4409, la escritura.
- `tests/test_viewer.py::test_on_disconnect_accepts_url_and_code` (REQ-VIEW-012).

## MODIFIED

### specs/prd/reflex-perspective.md → REQ-VIEW-010
- **Antes**: "SI se pierde la conexión … emitir `on_disconnect` y reintentar con espera
  exponencial (500 ms × 2ⁿ, tope 10 s)".
- **Después**: igual, "salvo lo dispuesto en REQ-VIEW-011".

### specs/prd/reflex-perspective.md → REQ-VIEW-005
- `on_disconnect` pasa a recibir `(url, code)` (REQ-VIEW-012).

### specs/prd/reflex-perspective.md → §6 Limitaciones
- Se retira "El puente no distingue el código de cierre del WebSocket".

### README.md → Events / Access control
- `on_disconnect(url, code)`; qué hace el visor ante 4401/4403/4409 y 4429.

## REMOVED

Ninguno.
