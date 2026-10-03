# Delta — WebSocket con autorización y en sólo lectura (0.2.0)

> Propuesta: [`proposal.md`](proposal.md) · Tareas: [`tasks.md`](tasks.md) · Analyze: [`analyze.md`](analyze.md)

## ADDED

### specs/prd/reflex-perspective.md → §4.2 Modo servidor

- **REQ-SRV-010** (evento): CUANDO se abra un WebSocket con `authorize` configurado y el
  `Origin` permitido, EL SISTEMA DEBERÁ esperar `authorize(websocket)` **antes de crear la
  sesión de Perspective**.
- **REQ-SRV-011** (no deseado): SI `authorize` devuelve un código, ENTONCES EL SISTEMA DEBERÁ
  aceptar el handshake, cerrar de inmediato con ese código y no crear la sesión; el cliente
  DEBERÁ recibir exactamente ese código.
- **REQ-SRV-012** (no deseado): SI `authorize` lanza una excepción o devuelve un código fuera
  de 4000–4999 (salvo 1008), ENTONCES EL SISTEMA DEBERÁ cerrar con 1011, registrar el error
  con `logger.exception`/`logger.error` y no crear la sesión.
- **REQ-SRV-013** (estado): MIENTRAS `read_only=True`, EL SISTEMA DEBERÁ reenviar al motor
  sólo los frames cuyo `Request` tenga **exactamente una** variante del `oneof client_req` y
  esa variante esté en la lista de lecturas de la versión de Perspective en uso.
- **REQ-SRV-014** (no deseado): SI, en sólo lectura, un frame no cumple REQ-SRV-013 (variante de
  escritura, desconocida, más de un campo fuera de `msg_id`/`entity_id`, o protobuf ilegible),
  ENTONCES EL SISTEMA DEBERÁ cerrar con `write_close_code` sin reenviar el frame, cerrar la
  sesión y registrar con `logger.warning` el número y nombre de la variante (nunca el
  contenido del frame).
- **REQ-SRV-015** (no deseado): SI se pide `read_only=True` y la versión instalada de
  `perspective-python` no tiene tabla de lecturas verificada y no se pasó `read_variants`,
  ENTONCES EL SISTEMA DEBERÁ lanzar `RuntimeError` al construir la app ASGI (o al llamar
  `serve()` directamente), antes de aceptar ninguna conexión.
- **REQ-SRV-016** (ubicuo): EL SISTEMA DEBERÁ seguir aceptando escrituras hechas desde Python
  (`PerspectiveHub.update/remove/clear/table/delete_table`, cliente local) con `read_only=True`.
- **REQ-SRV-017** (ubicuo): EL SISTEMA DEBERÁ aceptar `authorize`, `read_only`,
  `write_close_code` y `read_variants` en `serve()`, `asgi_app()`, `perspective_api()` y
  `mount()`, con valores por omisión que reproducen el comportamiento de 0.1.0.
- **REQ-SRV-018** (no deseado): SI `write_close_code` está fuera de 4000–4999, ENTONCES EL
  SISTEMA DEBERÁ lanzar `ValueError` al construir la app.

### specs/prd/reflex-perspective.md → §4.3 Versiones

- **REQ-VER-003** (ubicuo): EL SISTEMA DEBERÁ incluir una prueba de contrato que genere cada
  operación de lectura y de escritura con el cliente oficial de la versión pineada, compruebe
  su variante contra la tabla y falle si `PERSPECTIVE_VERSION` no tiene tabla.

### specs/api/server-api-v1.md → §1 (nuevos parámetros)

```python
Authorize = Callable[[WebSocket], int | None | Awaitable[int | None]]

async def PerspectiveHub.serve(
    websocket, executor=None, allowed_origins=None, *,
    authorize: Authorize | None = None,
    read_only: bool = False,
    write_close_code: int = 4409,
    read_variants: Collection[int] | None = None,
) -> None

PerspectiveHub.asgi_app(path=DEFAULT_PATH, executor=None, allowed_origins=None, *,
                        authorize=None, read_only=False, write_close_code=4409,
                        read_variants=None) -> Starlette
perspective_api(path=DEFAULT_PATH, hub=None, executor=None, allowed_origins=None, *, …mismos…)
mount(app, path=DEFAULT_PATH, hub=None, executor=None, allowed_origins=None, *, …mismos…)
```

Los parámetros nuevos son **sólo por palabra clave** (no cambian la posición de los actuales).
`authorize` puede ser síncrono o asíncrono (se espera si devuelve un awaitable).

### specs/api/server-api-v1.md → §1 (nuevos símbolos en `__all__`)

| Símbolo | Firma | Uso |
|---|---|---|
| `request_variant` | `request_variant(payload: bytes) -> int \| None` | Número de la única variante del `oneof`; `None` si el frame es ilegible o trae más de una |
| `is_read_request` | `is_read_request(payload: bytes, read_variants: Collection[int] \| None = None) -> bool` | Clasificador de REQ-SRV-013 (por omisión, la tabla de la versión instalada) |
| `READ_VARIANTS` | `Mapping[str, frozenset[int]]` | Lecturas verificadas por versión de Perspective |
| `WRITE_VARIANT_NAMES` | `Mapping[int, str]` | Nombres de las escrituras conocidas, para logs |
| `WRITE_CLOSE_CODE` | `4409` | Valor por omisión |

Públicos para que una app que componga su propio handler (p. ej. con tope de sesiones) no
copie el clasificador.

### specs/api/server-api-v1.md → §2.1 Códigos de cierre

| Código | Cuándo | Antes/después de `accept()` | REQ |
|---|---|---|---|
| 1008 | `Origin` no permitido | Antes (sin cambios) | REQ-SRV-003 |
| código de `authorize` (4000–4999 o 1008) | Autorización denegada | Después, sin sesión | REQ-SRV-011 |
| 1011 | `authorize` falló o devolvió un código inválido | Después, sin sesión | REQ-SRV-012 |
| `write_close_code` (4409) | Frame no permitido en sólo lectura | Con sesión; se cierra | REQ-SRV-014 |

### specs/api/server-api-v1.md → §2.2 (nuevo) Variantes de `Request` en Perspective 5.5.1

Lecturas permitidas en sólo lectura (`READ_VARIANTS["5.5.1"]`):

| N.º | Variante | N.º | Variante |
|---|---|---|---|
| 3 | `get_features_req` | 20 | `view_get_min_max_req` |
| 4 | `get_hosted_tables_req` | 21 | `view_on_update_req` |
| 5 | `table_make_port_req` ¹ | 22 | `view_remove_on_update_req` |
| 6 | `table_make_view_req` | 23 | `view_set_depth_req` |
| 7 | `table_schema_req` | 24 | `view_to_columns_string_req` |
| 8 | `table_size_req` | 25 | `view_to_csv_req` |
| 9 | `table_validate_expr_req` | 26 | `view_to_rows_string_req` |
| 10 | `view_column_paths_req` | 29 | `table_on_delete_req` |
| 11 | `view_delete_req` | 30 | `table_remove_delete_req` |
| 12 | `view_dimensions_req` | 34 | `view_on_delete_req` |
| 13 | `view_expression_schema_req` | 35 | `view_remove_delete_req` |
| 14 | `view_get_config_req` | 36 | `view_to_ndjson_string_req` |
| 15 | `view_schema_req` | 37 | `remove_hosted_tables_update_req` ² |
| 16 | `view_to_arrow_req` | 39 | `view_on_remove_req` |
| 17 | `server_system_info_req` | 40 | `view_remove_on_remove_req` |
| 18 | `view_collapse_req` | | |
| 19 | `view_expand_req` | | |

Escrituras (rechazadas): 27 `make_table_req`, 28 `table_delete_req`, 31 `table_remove_req`,
32 `table_replace_req` (también `clear`), 33 `table_update_req`, 38 `make_join_table_req`.

¹ El visor lo pide al conectar; un puerto sólo etiqueta el origen de futuras
actualizaciones, que siguen rechazadas. ² El visor lo manda al desmontarse; quita un
callback, no datos.
Fuente: `rust/perspective-client/perspective.proto` en el tag `v5.5.1`, verificado con el
cliente oficial el 2026-10-03.

### specs/technical/server-architecture.md → §3 Decisiones

#### DD-005: Orden de controles en `serve()`
`Origin` (1008, sin aceptar) → `authorize` (sin sesión) → `accept()` → si hubo código, cerrar
con él → crear sesión → por frame: descartar vacío/texto (REQ-SRV-004) → clasificar si
`read_only` → executor. La sesión de Perspective nunca existe para una conexión rechazada.

#### DD-006: Aceptar y cerrar para entregar el código de `authorize`
En un servidor ASGI real (uvicorn/granian), cerrar antes de `accept()` rechaza el handshake con
HTTP 403 y el navegador ve 1006: el código se pierde. Para que la app distinga "sin sesión"
de "sin permiso", se acepta y se cierra en el acto. Alternativa descartada: la extensión
`websocket.http.response` (respuesta HTTP de denegación), porque no todos los servidores la
implementan y el cliente de Perspective tampoco expone el estado HTTP.

#### DD-007: Clasificador estricto por lista de permitidos
Se recorren **todas** las etiquetas de nivel superior del frame (varints protobuf; tipos
0, 1, 2, 5). Se exige un único campo distinto de `msg_id` (1) y `entity_id` (2); cualquier
segundo campo, tipo de cable desconocido, longitud que sobrepase el frame o bytes sobrantes →
ilegible → rechazo. Motivo: en un `oneof` protobuf gana el último campo, así que mirar sólo el
primero permite anteponer una lectura a una escritura (reproducido con 5.5.1). Se descarta
decodificar con el `.proto` compilado: añade una dependencia y la librería no publica su
esquema en Python.

#### DD-008: Tabla de lecturas por versión, fallar cerrado
`READ_VARIANTS` se indexa por versión exacta (`"5.5.1"`). La versión se lee con
`importlib.metadata.version("perspective-python")`. Sin tabla para la versión instalada,
`read_only=True` no arranca (REQ-SRV-015) salvo `read_variants` explícito. Así una subida de
Perspective nunca deja el modo sólo lectura funcionando con números de otra versión.

### tests/test_server.py (nuevas pruebas, citan su REQ)

- `test_authorize_rejects_before_session` (REQ-SRV-010/011): `authorize` → 4401; el cliente
  recibe 4401 y `server.new_session` no se llama.
- `test_authorize_async_and_sync` (REQ-SRV-010).
- `test_authorize_error_closes_1011` y `test_authorize_invalid_code_closes_1011` (REQ-SRV-012).
- `test_read_only_allows_reads` (REQ-SRV-013): `open_table`, `size`, `schema`, `view`,
  `to_arrow`, `to_csv`, `on_update`, `on_remove`, `view.delete` con el cliente oficial.
- `test_read_only_rejects_each_write` parametrizada (REQ-SRV-014): `update`, `remove`, `replace`,
  `clear`, `make_table`, `join`, `table.delete` → 4409 y la tabla no cambia.
- `test_read_only_rejects_smuggled_write` (REQ-SRV-014): frame `size` + campo 33 → 4409 y la
  tabla no cambia.
- `test_read_only_rejects_unknown_and_malformed` (REQ-SRV-014): variante 99, varint truncado,
  longitud excedida.
- `test_read_only_unverified_version_fails` / `..._with_read_variants_ok` (REQ-SRV-015).
- `test_read_only_python_writes_still_work` (REQ-SRV-016).
- `test_params_pass_through_mount_and_api` (REQ-SRV-017), `test_defaults_unchanged` (REQ-SRV-017).
- `test_invalid_write_close_code` (REQ-SRV-018).
- `test_variant_contract_matches_pinned_version` (REQ-VER-003).

## MODIFIED

### specs/technical/server-architecture.md → §2 Componentes, fila `serve()`
- **Antes**: "Origen, sesión, reenvío de frames al motor, cola de salida · No hace: autenticar,
  filtrar escrituras".
- **Después**: "Origen, `authorize`, sesión, clasificación en sólo lectura, reenvío al motor,
  cola de salida · No hace: autorización por tabla, tope de sesiones".

### specs/technical/server-architecture.md → §4 Seguridad
- **Antes**: huecos "sin gancho de autorización" y "todo frame llega al motor".
- **Después**: mitigados por `authorize` (DD-006) y `read_only` (DD-007/008) cuando la app los
  activa; por omisión siguen abiertos (compatibilidad, Art. 4) y el README lo advierte.

### specs/prd/reflex-perspective.md → §6 Limitaciones
- **Antes**: "El WebSocket no autentica y es escribible".
- **Después**: "Por omisión el WebSocket no autentica y es escribible; `authorize` y
  `read_only=True` lo cierran. `read_only` no impide exportar lo que el usuario puede ver."

### README.md → Server-hosted tables / Notes
- **Antes**: "Apart from the Origin check, the WebSocket endpoint has no authentication … Put it
  behind your auth (e.g. a Starlette middleware in `api_transformer`)".
- **Después**: documenta `authorize` (firma, códigos, por qué se acepta y cierra), `read_only`
  (qué rechaza, 4409, escrituras desde Python intactas, incompatibilidad con `edit_mode="EDIT"`,
  `update_rows`, `remove_keys` y `rp.update/remove/replace/clear` en visores de servidor) y
  recomienda **los dos** en cualquier despliegue con más de un usuario. Ejemplo con `mount()`.

### pyproject.toml / `__init__.py`
- `version` y `__version__`: `0.1.0` → `0.2.0`.

## REMOVED

Ninguno.

## Uso esperado (consola de CuidaSalud)

```python
from reflex_perspective import server as ps

async def autorizar_panel(ws):            # cookie cs_session + rol → None | 4401 | 4403 | 4429
    ...

ps.mount(
    app,
    path="/analitica/ws",
    allowed_origins=[settings.CS_BASE_URL],
    executor=executor_analitica,
    authorize=autorizar_panel,
    read_only=True,
)
```

Con réplicas y tope de vistas, la consola sigue con su ruta propia pero delega en la librería:
`await panel.hubs[i].serve(ws, executor=..., allowed_origins=..., authorize=..., read_only=True)`.
