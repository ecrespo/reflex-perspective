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
| [`2026-10-ws-authorize-read-only/`](_archivo/2026-10-ws-authorize-read-only/) | 0.2.0 | `authorize` y `read_only` en el WebSocket; clasificador estricto por lista de permitidos |
| [`2026-10-perspective-version-guard/`](_archivo/2026-10-perspective-version-guard/) | 0.2.0 | CI verifica que npm y `perspective-python` estén en la misma versión; Dependabot deja de subir `perspective-python` |

## Diferidos (sin carpeta aún)

Ver la fase 9 de [`plan.md`](plan.md): cierres 44xx en el puente (P-02 / A-08 / A-09), tope de
sesiones y `on_reject` (P-03 / A-11) y la subida de Perspective cuando se publique
`table_describe_req` (41), siguiendo `specs/runbooks/perspective-upgrade.md`.
