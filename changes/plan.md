# Plan de implementación — 0.2.0 y diferidos

> Fecha: 2026-10-03 · Rama de trabajo: `feature/0.2.0` (sale de `develop`, vuelve por PR)
> Cambios: [`2026-10-ws-authorize-read-only/`](2026-10-ws-authorize-read-only/),
> [`2026-10-perspective-version-guard/`](2026-10-perspective-version-guard/)
> Regla: cada fase se implementa con TDD y se espera aprobación antes de la siguiente.

Estados: `[ ]` pendiente · `[~]` en curso · `[x]` hecha · `[!]` bloqueada.

| Fase | Estado | Tareas | Entrega | Depende de | Hecho cuando |
|---|---|---|---|---|---|
| 0 · Preparación | `[x]` | — | Artefactos SDD versionados; propuestas aprobadas; constitución ratificada; P-01 resuelta; `tests/test_specs.py` (guardas del Art. 7) | — | `pytest tests/test_specs.py` en verde |
| 1 · Guardia de versiones | `[x]` | V-001, V-002 | Paso de CI que compara los tres pines; Dependabot ignora `perspective-python` | 0 | `PERSPECTIVE_VERSION="5.5.0"` hace fallar Quality |
| 2 · Clasificador | `[x]` | T-001 (+ helper A-10) | `request_variant`, `is_read_request`, `READ_VARIANTS`, `WRITE_VARIANT_NAMES`, `WRITE_CLOSE_CODE`; helper de pruebas con `perspective.Client` | 0 | Pruebas del clasificador en verde |
| 3 · Contrato y `authorize` | `[ ]` | T-002 ∥ T-003 | Prueba de contrato (REQ-VER-003); `authorize` en `serve()` (DD-005/006) | 2 | Pruebas de `authorize` y `-k contract` en verde |
| 4 · `read_only` | `[ ]` | T-004 | Clasificación por frame, 4409, guardia de versión, `read_variants` | 2, 3 | Pruebas `test_read_only_*` en verde |
| 5 · API pública | `[ ]` | T-005 | Parámetros en `asgi_app`/`perspective_api`/`mount`; validaciones; `__all__` | 3, 4 | `test_defaults_unchanged`, ruff limpio |
| 6 · Validación y docs | `[ ]` | T-006 ∥ T-007 | Pase en navegador con la demo en sólo lectura; README; `CHANGELOG.md` | 5 | Sin 4409 en lectura; variantes anotadas |
| 7 · Plegado SDD | `[ ]` | T-008, V-003 | Deltas en `specs/`; `0.2.0`; carpetas a `_archivo/` | 1, 6 | Quality y Security en verde; REQ en `specs/` |
| 8 · Release 0.2.0 | `[ ]` | T-009 | PR a `main`, tag `v0.2.0` (el tag lo empuja el mantenedor) | 7 | 0.2.0 en PyPI y release en GitHub |
| 9 · Diferidos | `[ ]` | ver abajo | Cambios posteriores a 0.2.0, cada uno con su propuesta | 8 | Cada sub-fase publicada y plegada |

## Fase 9 — Diferidos

Cada sub-fase arranca con su carpeta en `changes/` (proposal + delta-spec + tasks, Art. 7) y
sólo se implementa tras aprobarla.

| Sub-fase | Origen | Alcance | Versión objetivo | Bloqueo |
|---|---|---|---|---|
| 9a · Cierres 44xx en el puente | P-02, A-08, A-09 | Envolver el WebSocket del cliente en `perspective_viewer.jsx` para leer `CloseEvent.code`; no reintentar 4400–4499; pasar el código a `on_disconnect`; aviso en la consola del navegador ante 4409 | 0.3.0 | — |
| 9b · Tope de sesiones y rechazos | P-03, A-11 | Tope de sesiones por hub (4429) y gancho `on_reject(code)` para métricas, con valores por omisión que no cambian 0.2.0 | 0.3.0 | Confirmar con la consola de CuidaSalud que lo necesita en la librería |
| 9c · Subida de Perspective | Diferido de `changes/README.md` | Seguir `specs/runbooks/perspective-upgrade.md`: tabla `READ_VARIANTS[<nueva>]` con 41 `table_describe_req` y 9 `reserved` | patch | Esperar a que npm y PyPI publiquen la versión con el campo 41 |

## Registro

| Fecha | Fase | Resultado | Notas |
|---|---|---|---|
| 2026-10-03 | 0 | hecha | `tests/test_specs.py` rojo → verde tras la aprobación del mantenedor; P-01 queda con la respuesta propuesta ("ambas"), aprobada con la propuesta |
| 2026-10-03 | 1 | hecha | `scripts/check_perspective_versions.py` + paso en `build`; `ignore` en Dependabot; 4 pruebas rojo → verde; `5.5.0` local → exit 1. Pendiente tras el push: confirmar en *Insights → Dependabot* que el YAML valida. También se formateó el ejemplo de `delta-spec.md` (ruff formatea Markdown y habría roto Lint) |
| 2026-10-03 | 2 | hecha | `request_variant`, `is_read_request`, `READ_VARIANTS["5.5.1"]` (32 lecturas), `WRITE_VARIANT_NAMES`, `WRITE_CLOSE_CODE`; helper `Recorder` (A-10); 71 pruebas rojo → verde. Variantes del cliente oficial medidas = §2.2 |
