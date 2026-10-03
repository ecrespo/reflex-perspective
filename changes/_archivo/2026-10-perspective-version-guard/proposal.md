# Propuesta — Guardia de versiones de Perspective

> Estado: **implementada** (0.2.0, 2026-10-03; aprobada por Ernesto Crespo el 2026-10-03) · Fecha: 2026-10-03 · Autor: Ernesto Crespo (mantenedor)
> Specs base afectadas: `specs/prd/reflex-perspective.md` §4.3, `specs/constitution.md` Art. 3
> Versión objetivo: **0.2.0** (junto con `2026-10-ws-authorize-read-only`)

## Problema

Revisión de versiones del 2026-10-03:

| Pieza | Fijada | Última publicada | Nota |
|---|---|---|---|
| `@perspective-dev/*` (npm) | 5.5.1 | 5.5.1 (2026-09-18) | Al día |
| `perspective-python` | 5.5.1 | 5.5.1 | Al día |
| `reflex` | ≥ 0.9.12 | 0.9.12 | Al día |
| `perspective.proto` en `master` | — | sin publicar | Campo 9 → `reserved`; nuevo 41 `table_describe_req` |

No hay que subir nada hoy, pero el repo no protege el Art. 3:

1. **Dependabot** (`.github/dependabot.yml`, ecosistema `uv`, grupo `python` con `"*"`) puede
   abrir un PR que suba `perspective-python` sin tocar `PERSPECTIVE_VERSION` (npm). Si se
   mergea, cliente y servidor hablan protocolos distintos y, con el modo sólo lectura, la
   tabla de variantes deja de corresponder.
2. **Nada en CI** comprueba que `perspective-python==X` en `pyproject.toml` (extras `server` y
   `dev`) sea igual a `PERSPECTIVE_VERSION`.
3. El próximo release de Perspective trae un cambio de protocolo ya visible en `master`.

## Alcance

- Dependabot ignora `perspective-python` (se sube a mano con el runbook).
- Paso de CI que compara los tres pines (`server`, `dev`, `PERSPECTIVE_VERSION`).
- Runbook `specs/runbooks/perspective-upgrade.md` (ya redactado en `specs/`).

**Fuera de alcance**: subir Perspective (no hay versión nueva); actualizar acciones de GitHub
(Dependabot ya lo hace).

## Impacto

Sólo afecta a CI y a Dependabot; ningún cambio para los consumidores.

## Constitution check

Art. 3 pasa de convención a regla verificada por CI. Art. 1: el paso nuevo forma parte de
**Quality**.
