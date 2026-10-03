# Tasks — Guardia de versiones de Perspective

> Specs de origen: [`proposal.md`](proposal.md), [`delta-spec.md`](delta-spec.md),
> `specs/runbooks/perspective-upgrade.md` · Generado: 2026-10-03

### [x] 2026-10-03 V-001 · Paso de CI de versiones sincronizadas [P]
- **Qué**: paso en el job `build` de `ci.yml` (mismo estilo que "Check versions are in sync").
- **REQ**: REQ-VER-004
- **Archivos**: `.github/workflows/ci.yml`
- **Done**: en una rama, cambiar `PERSPECTIVE_VERSION` a `5.5.0` hace fallar **Quality** con el
  mensaje de las tres versiones; revertido, pasa.

### [x] 2026-10-03 V-002 · Dependabot ignora `perspective-python` [P]
- **REQ**: REQ-VER-005
- **Archivos**: `.github/dependabot.yml`
- **Done**: el archivo valida (pestaña *Insights → Dependency graph → Dependabot* sin errores).

### [x] 2026-10-03 V-003 · Plegar el delta
- **Qué**: REQ-VER-004/005 al PRD; enmienda del Art. 3 en la constitución (tabla de enmiendas).
- **Depende de**: V-001, V-002
- **Done**: `grep -n "REQ-VER-00[45]" specs/prd/reflex-perspective.md` encuentra ambos.

## Matriz de trazabilidad

| REQ | Tareas | Verificación |
|---|---|---|
| REQ-VER-004 | V-001 | `tests/test_versions.py` (repo, `5.5.0`, pin ausente) + paso de CI |
| REQ-VER-005 | V-002 | `test_dependabot_ignores_perspective_python`; GitHub validó el archivo (check `.github/dependabot.yml` en PR #4) |
