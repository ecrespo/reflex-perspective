# Delta — Guardia de versiones de Perspective

## ADDED

### specs/prd/reflex-perspective.md → §4.3 Versiones
- **REQ-VER-004** (no deseado): SI `perspective-python` en los extras `server` o `dev` de
  `pyproject.toml` difiere de `PERSPECTIVE_VERSION`, ENTONCES el workflow **Quality** DEBERÁ
  fallar con un error que nombre las tres versiones.
- **REQ-VER-005** (ubicuo): Dependabot NO DEBERÁ proponer actualizaciones de
  `perspective-python`; la subida sigue `specs/runbooks/perspective-upgrade.md`.

### .github/workflows/ci.yml → job `build`
- Paso "Check Perspective versions are in sync": lee `PERSPECTIVE_VERSION` de
  `viewer.py` y los dos `perspective-python==` de `pyproject.toml`; falla si no son iguales.

### .github/dependabot.yml → ecosistema `uv`
```yaml
    ignore:
      - dependency-name: "perspective-python"
```

### specs/runbooks/perspective-upgrade.md
- Nuevo (ya en `specs/`): detección, revisión del `.proto`, tabla de variantes, pase en
  navegador, publicación.

## MODIFIED

### specs/constitution.md → Art. 3
- **Antes**: "Toda subida DEBERÁ seguir el runbook".
- **Después**: igual, y "CI DEBERÁ verificar la igualdad de los pines (REQ-VER-004)".

## REMOVED

Ninguno.
