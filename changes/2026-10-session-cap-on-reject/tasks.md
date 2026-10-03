# Tasks — Tope de sesiones y gancho de rechazos (0.3.0)

> Specs de origen: [`proposal.md`](proposal.md), [`delta-spec.md`](delta-spec.md) · Generado: 2026-10-03

Estados: `[ ]` pendiente · `[~]` en curso · `[x] {fecha}` hecha · `[!]` bloqueada (nota).

### [ ] S-001 · `session_count` y `max_sessions`
- **Qué**: contador por hub bajo su lock; tope evaluado tras `authorize`; 4429 con aceptar y
  cerrar; validación de `max_sessions`.
- **REQ**: REQ-SRV-019, REQ-SRV-022, REQ-SRV-023
- **Done**: `test_max_sessions_refuses_with_4429`, `test_cap_checked_after_authorize`,
  `test_session_count`, `test_invalid_max_sessions` en verde.

### [ ] S-002 · `on_reject`
- **Qué**: llamada en cada cierre de rechazo (1008, `authorize`, 1011, `write_close_code`, 4429);
  síncrono o asíncrono; errores registrados sin cambiar el cierre.
- **REQ**: REQ-SRV-020, REQ-SRV-021
- **Depende de**: S-001
- **Done**: `test_on_reject_reports_each_code`, `test_on_reject_error_keeps_close_code` en verde.

### [ ] S-003 · Paso de parámetros y documentación
- **Qué**: `asgi_app`, `perspective_api`, `mount`; `test_defaults_unchanged` ampliada; README,
  CHANGELOG; la demo cuenta rechazos con `on_reject` en lugar del filtro del logger.
- **REQ**: REQ-SRV-017
- **Depende de**: S-002

## Matriz de trazabilidad

| REQ | Tareas | Tests |
|---|---|---|
| REQ-SRV-019 | S-001 | test_max_sessions_refuses_with_4429, test_cap_checked_after_authorize |
| REQ-SRV-020 | S-002 | test_on_reject_reports_each_code |
| REQ-SRV-021 | S-002 | test_on_reject_error_keeps_close_code |
| REQ-SRV-022 | S-001 | test_session_count |
| REQ-SRV-023 | S-001 | test_invalid_max_sessions |

## Registro de ejecución

| Fecha | Tareas | Resultado | Notas |
|---|---|---|---|
