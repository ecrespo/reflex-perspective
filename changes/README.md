# changes/ — propuestas activas

Cada cambio a lo especificado en [`../specs/`](../specs/) vive aquí como `proposal.md` +
`delta-spec.md` + `tasks.md` (y `analyze.md` cuando aplica). Al publicarse la versión que lo
implementa, el delta se pliega a `specs/` en el mismo PR y la carpeta pasa a `_archivo/`.
Un `REQ-ID` retirado no se reutiliza. Las propuestas llegan a `develop` ya aprobadas (la
revisión ocurre en su PR); `tests/test_specs.py` lo comprueba.

Orden de implementación por fases: [`plan.md`](plan.md).

## Abiertos

| Carpeta | Versión | Estado | Resumen |
|---|---|---|---|
| [`2026-10-ws-authorize-read-only/`](2026-10-ws-authorize-read-only/) | 0.2.0 | aprobada · Analyze: listo | `authorize` y `read_only` en el WebSocket; clasificador estricto por lista de permitidos. Origen: borrador de la consola de CuidaSalud (DD-017) |
| [`2026-10-perspective-version-guard/`](2026-10-perspective-version-guard/) | 0.2.0 | aprobada | CI verifica que npm y `perspective-python` estén en la misma versión; Dependabot deja de subir `perspective-python` |

## Diferidos (sin carpeta aún)

- Puente JSX: no reintentar ante cierres 4400–4499 y pasar el código a `on_disconnect`
  (P-02 / A-08).
- Subir Perspective a la versión que publique `table_describe_req` (41): seguir
  `specs/runbooks/perspective-upgrade.md` cuando salga.
