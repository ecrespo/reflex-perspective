# Runbook — subir de versión Perspective

> Aplica el Art. 3 de la constitución. Última revisión: 2026-10-03 (versión vigente 5.5.1).

Perspective publica a la vez los paquetes npm `@perspective-dev/*` y `perspective-python`, y
cambia su protocolo protobuf entre versiones. Por eso se suben **juntos y a mano**; Dependabot
no debe proponer `perspective-python` por separado
(CI lo verifica con `scripts/check_perspective_versions.py`; ver
[`changes/_archivo/2026-10-perspective-version-guard/`](../../changes/_archivo/2026-10-perspective-version-guard/)).

## 1. Detectar una versión nueva

```bash
npm view @perspective-dev/client dist-tags          # "latest"
pip index versions perspective-python | head -1
```
Las dos deben coincidir. Si npm va por delante de PyPI (o al revés), esperar.

## 2. Revisar el protocolo

Comparar el `message Request` de
`rust/perspective-client/perspective.proto` entre el tag actual y el nuevo:

```
https://raw.githubusercontent.com/perspective-dev/perspective/v<ACTUAL>/rust/perspective-client/perspective.proto
https://raw.githubusercontent.com/perspective-dev/perspective/v<NUEVA>/rust/perspective-client/perspective.proto
```

Para cada variante del `oneof client_req` añadida, renumerada o `reserved`:
- clasificarla como **lectura** o **escritura** (¿modifica una tabla o crea/borra una?);
- añadir la tabla de la versión nueva en el clasificador de sólo lectura
  (`_READ_VARIANTS[<NUEVA>]`), sin tocar la de la versión anterior.

Comprobar también el transporte del navegador,
`packages/perspective/src/ts/websocket.ts` (o la ruta equivalente) del tag nuevo: `onclose`
debe seguir llamando `client.handle_error("WebSocket closed " + event.code, …)`. El puente lee
el código de ese texto (`closeCodeFromError`); si cambia, actualizar la función y
`tests/js/bridge.test.mjs`. Si no se actualiza, el código llega como `None` y el visor vuelve a
reintentar todo cierre (comportamiento de 0.2.0).

**Cambio ya visible en `master` (después de 5.5.1, sin publicar al 2026-10-03):** el campo
**9** `table_validate_expr_req` pasa a `reserved` y lo reemplaza **41**
`table_describe_req` (lectura). La próxima versión necesitará su propia tabla.

## 3. Cambiar las versiones

1. `PERSPECTIVE_VERSION` en `custom_components/reflex_perspective/viewer.py`.
2. `perspective-python==<NUEVA>` en los extras `server` y `dev` de `pyproject.toml`.
3. `uv lock` y regenerar `viewer.pyi` si cambian props (`reflex component build`).
4. Versiones del README ("Built against …").

## 4. Verificar

```bash
uv sync --extra dev && uv run pytest -ra       # incluye la prueba de contrato de variantes
cd perspective_demo && uv run reflex run        # pase manual en navegador
```
Pase en navegador con la demo en `read_only=True`: abrir `/server`, cambiar plugin, agrupar,
expandir/colapsar filas, cambiar profundidad, abrir un workspace y cerrar la pestaña. El log
`reflex_perspective.server` no debe mostrar ningún cierre 4409. Anotar las variantes vistas en
el PR.

## 5. Publicar

Subir `version` (patch si sólo cambia Perspective) y seguir "Releasing" del README. Avisar a
los consumidores que fijan versión (consola de CuidaSalud): deben subir
`reflex-perspective[server]` y nada más; las dos piezas de Perspective vienen con ella.
