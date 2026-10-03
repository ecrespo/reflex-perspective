# Delta — Tope de sesiones y gancho de rechazos (0.3.0)

> Propuesta: [`proposal.md`](proposal.md) · Tareas: [`tasks.md`](tasks.md)

## ADDED

### specs/prd/reflex-perspective.md → §4.2 Modo servidor

- **REQ-SRV-019** (no deseado): SI `max_sessions` está configurado y el hub ya tiene ese número de
  sesiones WebSocket abiertas, ENTONCES EL SISTEMA DEBERÁ aceptar el handshake, cerrar con 4429
  y no crear la sesión; el control DEBERÁ evaluarse después de `Origin` y `authorize`.
- **REQ-SRV-020** (evento): CUANDO el sistema rechace una conexión o cierre por un frame no
  permitido, EL SISTEMA DEBERÁ llamar `on_reject(code, websocket)` si está configurado (síncrono
  o asíncrono), con el código del cierre.
- **REQ-SRV-021** (no deseado): SI `on_reject` lanza una excepción, ENTONCES EL SISTEMA DEBERÁ
  registrarla con `logger.exception` y cerrar igualmente con el código previsto.
- **REQ-SRV-022** (ubicuo): EL SISTEMA DEBERÁ exponer `PerspectiveHub.session_count` con el número
  de sesiones WebSocket abiertas, que DEBERÁ volver a su valor al cerrarse cada sesión.
- **REQ-SRV-023** (no deseado): SI `max_sessions` no es un entero ≥ 1, ENTONCES EL SISTEMA DEBERÁ
  lanzar `ValueError` al construir la app (o al llamar `serve()`).

### specs/api/server-api-v1.md → §1 y §2.1

```python
OnReject = Callable[[int, WebSocket], Awaitable[None] | None]

async def PerspectiveHub.serve(..., *, authorize=None, read_only=False,
    write_close_code=4409, read_variants=None,
    max_sessions: int | None = None, on_reject: OnReject | None = None) -> None
PerspectiveHub.session_count -> int   # propiedad
```

| Código | Cuándo | Antes/después de `accept()` | REQ |
|---|---|---|---|
| 4429 | Tope de sesiones alcanzado | Después, sin sesión | REQ-SRV-019 |

### specs/technical/server-architecture.md → §3

#### DD-009: Tope y métricas dentro de `serve()`
Orden: `Origin` → `authorize` → tope → `accept()` → sesión. El contador vive en el hub (protegido
por su lock) y se libera en el `finally` de la sesión. `on_reject` se llama justo antes de cada
cierre de rechazo; sus errores se registran y nunca cambian el código ni reabren la conexión.

### tests/test_server.py

- `test_max_sessions_refuses_with_4429` (REQ-SRV-019): con `max_sessions=1`, la segunda
  conexión recibe 4429, no se crea su sesión y, al cerrar la primera, una nueva entra.
- `test_cap_checked_after_authorize` (REQ-SRV-019).
- `test_on_reject_reports_each_code` parametrizada (REQ-SRV-020): 1008, 4401, 1011, 4409, 4429;
  sync y async.
- `test_on_reject_error_keeps_close_code` (REQ-SRV-021).
- `test_session_count` (REQ-SRV-022).
- `test_invalid_max_sessions` (REQ-SRV-023).
- `test_defaults_unchanged` ampliada (REQ-SRV-017) con `max_sessions` y `on_reject`.

## MODIFIED

### specs/prd/reflex-perspective.md → REQ-SRV-017
- Añade `max_sessions` y `on_reject` a las opciones con valores por omisión de 0.2.0.

### specs/technical/server-architecture.md → §2, fila `serve()`
- **Antes**: "No hace: autorización por tabla, tope de sesiones".
- **Después**: "No hace: autorización por tabla".

## REMOVED

Ninguno.
