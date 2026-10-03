# changes/ — propuestas activas

Cada cambio a lo especificado en [`../specs/`](../specs/) vive aquí como `proposal.md` +
`delta-spec.md` + `tasks.md` (y `analyze.md` cuando aplica). Al publicarse la versión que lo
implementa, el delta se pliega a `specs/` en el mismo PR y la carpeta pasa a `_archivo/`.
Un `REQ-ID` retirado no se reutiliza. Las propuestas llegan a `develop` ya aprobadas (la
revisión ocurre en su PR); `tests/test_specs.py` lo comprueba.

Orden de implementación por fases: [`plan.md`](plan.md).

## Abiertos

Ninguno.

## Archivados

| Carpeta | Versión | Resumen |
|---|---|---|
| [`2026-10-bridge-close-codes/`](_archivo/2026-10-bridge-close-codes/) | 0.3.0 | El puente no reintenta cierres 4400–4499 (salvo 4429), avisa en consola y `on_disconnect(url, code)` |
| [`2026-10-session-cap-on-reject/`](_archivo/2026-10-session-cap-on-reject/) | 0.3.0 | `max_sessions` (4429), `on_reject(code, websocket)` y `hub.session_count` |
| [`2026-10-ws-authorize-read-only/`](_archivo/2026-10-ws-authorize-read-only/) | 0.2.0 | `authorize` y `read_only` en el WebSocket; clasificador estricto por lista de permitidos |
| [`2026-10-perspective-version-guard/`](_archivo/2026-10-perspective-version-guard/) | 0.2.0 | CI verifica que npm y `perspective-python` estén en la misma versión; Dependabot deja de subir `perspective-python` |

## Diferidos (sin carpeta aún)

- Subir Perspective a la versión que publique `table_describe_req` (41) (fase 9c de
  [`plan.md`](plan.md)): bloqueado; al 2026-10-03 npm y PyPI siguen en 5.5.1. Seguir
  `specs/runbooks/perspective-upgrade.md` cuando salga.
