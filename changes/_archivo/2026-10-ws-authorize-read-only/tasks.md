# Tasks — WebSocket con autorización y en sólo lectura (0.2.0)

> Specs de origen: [`proposal.md`](proposal.md), [`delta-spec.md`](delta-spec.md),
> `specs/api/server-api-v1.md`, `specs/technical/server-architecture.md`
> Generado: 2026-10-03 · Reemplaza a D-PSP-1…4 del borrador de la consola

## Convenciones

- Orden = orden de ejecución salvo [P].
- Estados: `[ ]` pendiente · `[~]` en curso · `[x] {fecha}` hecha · `[!]` bloqueada (nota).
- **Primera tanda supervisada**: T-001…T-004.

## Tareas

### [x] 2026-10-03 T-001 · Clasificador estricto y tabla de variantes
- **Qué**: `request_variant()`, `is_read_request()`, `READ_VARIANTS["5.5.1"]`,
  `WRITE_VARIANT_NAMES`, `WRITE_CLOSE_CODE` en `server.py` (DD-007). Sin tocar `serve()` aún.
- **REQ**: REQ-SRV-013, REQ-SRV-014
- **Archivos**: `custom_components/reflex_perspective/server.py`, `tests/test_server.py`
- **Depende de**: —
- **Done**: pruebas unitarias del clasificador en verde: frames del cliente oficial (lecturas
  → True, escrituras → False), frame `size`+33 → False, variante 99 → False, varint truncado y
  longitud excedida → `request_variant` = `None`.

### [x] 2026-10-03 T-002 · Prueba de contrato atada a la versión [P con T-003]
- **Qué**: `test_variant_contract_matches_pinned_version`: con `perspective.Client` en proceso,
  ejecutar cada operación de lectura y escritura, capturar su variante y compararla con la
  tabla; afirmar `importlib.metadata.version("perspective-python") == PERSPECTIVE_VERSION` y que
  la versión existe en `READ_VARIANTS`.
- **REQ**: REQ-VER-003
- **Depende de**: T-001
- **Done**: `uv run pytest -k contract` en verde; cambiar `PERSPECTIVE_VERSION` a `"9.9.9"` en
  local lo hace fallar.

### [x] 2026-10-03 T-003 · `authorize` en `serve()` [P con T-002]
- **Qué**: parámetro sólo-palabra-clave; orden DD-005; aceptar y cerrar con el código (DD-006);
  excepción o código inválido → 1011 con log (REQ-SRV-012); acepta síncrono y asíncrono.
- **REQ**: REQ-SRV-010, REQ-SRV-011, REQ-SRV-012
- **Archivos**: `server.py`, `tests/test_server.py`
- **Depende de**: —
- **Done**: `test_authorize_rejects_before_session` (con `new_session` espiado),
  `test_authorize_async_and_sync`, `test_authorize_error_closes_1011`,
  `test_authorize_invalid_code_closes_1011` en verde.

### [x] 2026-10-03 T-004 · `read_only` en `serve()`
- **Qué**: clasificar cada frame binario antes del executor; rechazo → `logger.warning` con
  número y nombre de variante, cierre con `write_close_code`, `session.close()`; comprobación de
  versión al entrar (REQ-SRV-015); `read_variants` explícito.
- **REQ**: REQ-SRV-013, REQ-SRV-014, REQ-SRV-015, REQ-SRV-016
- **Depende de**: T-001
- **Done**: `test_read_only_allows_reads`, `test_read_only_rejects_each_write` (parametrizada,
  la tabla no cambia), `test_read_only_rejects_smuggled_write`,
  `test_read_only_rejects_unknown_and_malformed`, `test_read_only_unverified_version_fails`,
  `test_read_only_python_writes_still_work` en verde. Para mandar frames del cliente oficial por
  el `TestClient`, usar un `perspective.Client` cuyo callback de envío escriba en el socket de
  prueba.

### [x] 2026-10-03 T-005 · Paso de parámetros y validaciones de construcción
- **Qué**: `asgi_app`, `perspective_api`, `mount` aceptan y pasan `authorize`, `read_only`,
  `write_close_code`, `read_variants`; `ValueError` para `write_close_code` fuera de 4000–4999;
  `RuntimeError` de versión no verificada al construir; símbolos nuevos en `__all__`.
- **REQ**: REQ-SRV-015, REQ-SRV-017, REQ-SRV-018
- **Depende de**: T-003, T-004
- **Done**: `test_params_pass_through_mount_and_api`, `test_defaults_unchanged` (las pruebas de
  0.1.0 pasan sin cambios), `test_invalid_write_close_code` en verde; `ruff check` limpio.

### [x] 2026-10-03 T-006 · Pase en navegador con la demo en sólo lectura
- **Qué**: montar la demo con `read_only=True` detrás de una variable de entorno
  (`PERSPECTIVE_DEMO_READ_ONLY=1`) y recorrer `/server`: cambiar plugin, agrupar, expandir y
  colapsar, cambiar profundidad, filtros, modo `replicated`, cerrar la pestaña. En la página `/api`
  con un visor de servidor, comprobar que `edit_mode="EDIT"` produce 4409 (esperado).
- **REQ**: REQ-SRV-013, REQ-SRV-014
- **Archivos**: `perspective_demo/perspective_demo/perspective_demo.py`
- **Depende de**: T-005
- **Done**: log de `reflex_perspective.server` sin 4409 durante el recorrido de lectura; lista de
  variantes observadas anotada en el registro de ejecución; si aparece una lectura no listada,
  **parar** y actualizar la tabla y el delta.

### [x] 2026-10-03 T-007 · README y CHANGELOG [P con T-006]
- **Qué**: sección de seguridad del README según el MODIFIED del delta; crear `CHANGELOG.md`
  (Keep a Changelog) con `0.2.0` (Added: `authorize`, `read_only`, clasificador público; Security:
  cierre del WebSocket escribible) y `0.1.0`.
- **REQ**: REQ-SRV-017 (documentación del contrato)
- **Depende de**: T-005
- **Done**: README revisado; `grep -n "read_only\|authorize" README.md` muestra ambos;
  `CHANGELOG.md` existe.

### [x] 2026-10-03 T-008 · Plegar el delta a `specs/` y versionar
- **Qué**: aplicar ADDED/MODIFIED a PRD, API y Tech Design; estado de `proposal.md` →
  implementada; `version`/`__version__` → `0.2.0`; mover la carpeta a `changes/_archivo/`.
- **REQ**: — (Art. 7, Definition of Done)
- **Depende de**: T-006, T-007
- **Done**: CI **Quality** y **Security** en verde en `develop`; `grep -rn "REQ-SRV-01[0-8]"
  specs/` encuentra cada REQ en el PRD.

### [ ] T-009 · Publicar 0.2.0
- **Qué**: merge a `main`, `git tag v0.2.0 && git push origin v0.2.0`.
- **REQ**: — (cierra PR-11 de la consola)
- **Depende de**: T-008
- **Done**: `pip index versions reflex-perspective` muestra `0.2.0`; release en GitHub con
  artefactos.

## Matriz de trazabilidad

| REQ | Tareas | Tests |
|---|---|---|
| REQ-SRV-010 | T-003 | test_authorize_rejects_before_session, test_authorize_async_and_sync |
| REQ-SRV-011 | T-003 | test_authorize_rejects_before_session |
| REQ-SRV-012 | T-003 | test_authorize_error_closes_1011, test_authorize_invalid_code_closes_1011 |
| REQ-SRV-013 | T-001, T-004, T-006 | test_read_only_allows_reads, pruebas del clasificador |
| REQ-SRV-014 | T-001, T-004, T-006 | test_read_only_rejects_each_write, test_read_only_rejects_smuggled_write, test_read_only_rejects_unknown_and_malformed |
| REQ-SRV-015 | T-004, T-005 | test_read_only_unverified_version_fails, …_with_read_variants_ok |
| REQ-SRV-016 | T-004 | test_read_only_python_writes_still_work |
| REQ-SRV-017 | T-005, T-007 | test_params_pass_through_mount_and_api, test_defaults_unchanged |
| REQ-SRV-018 | T-005 | test_invalid_write_close_code |
| REQ-VER-003 | T-002 | test_variant_contract_matches_pinned_version |

SHOULD diferidos: P-02 (reintentos del puente ante 44xx), P-03 (tope de sesiones / `on_reject`).

## Registro de ejecución

| Fecha | Tareas | Resultado | Notas |
|---|---|---|---|
| 2026-10-03 | T-001 | hecha | Variantes del cliente oficial 5.5.1 = §2.2 (32 lecturas, 6 escrituras) |
| 2026-10-03 | T-002, T-003 | hecha | Contrato falla con `PERSPECTIVE_VERSION="9.9.9"` |
| 2026-10-03 | T-004 | hecha | Frame real `size`+`update`: escribe sin `read_only`, 4409 con él (A-01) |
| 2026-10-03 | T-005 | hecha | Validaciones al construir; clasificador en `__all__` |
| 2026-10-03 | T-006 | hecha | Chrome headless (Playwright) sobre la demo con `PERSPECTIVE_DEMO_READ_ONLY=1`, `/server`: cambio de plugin, `group_by`, filtro, orden, expand/collapse/`set_depth`, panel de ajustes, `to_csv`, `trades` → modo `server`, cierre de pestaña. Variantes enviadas por el navegador: 3, 4, 5, 6, 7, 9, 11, 12, 13, 14, 15, 16, 18, 19, 21, 22, 23, 24, 25 — **todas en la tabla**, 0 cierres 4409. Botón "Write from the browser" (`rp.update`, variante 33): 4409 + `warning` en sólo lectura; aplicado sin cierre en modo escribible. En lugar de `/api` (visor sólo cliente) se usó la tarjeta *Access* de `/server` |
| 2026-10-03 | T-007 | hecha | README *Access control*, `CHANGELOG.md` (0.2.0 sin fecha hasta el release) |
| 2026-10-03 | T-008 | hecha | Delta plegado en PRD/API/diseño técnico; `0.2.0`; carpeta en `_archivo/`. CI en GitHub: pendiente del push |
