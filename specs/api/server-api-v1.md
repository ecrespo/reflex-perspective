# API — `reflex_perspective.server` v1

> Versión de la spec: 1.2 (librería `0.3.0`) · Fecha: 2026-10-03
> PRD: [`../prd/reflex-perspective.md`](../prd/reflex-perspective.md) §4.2

Contrato público del módulo servidor. Requiere el extra `server`
(`pip install "reflex-perspective[server]"`); importarlo sin `perspective-python` lanza
`ImportError` con la instrucción de instalación.

## 1. Funciones y clases públicas (`__all__`)

| Símbolo | Firma | REQ |
|---|---|---|
| `DEFAULT_PATH` | `"/perspective"` | REQ-SRV-002 |
| `PerspectiveHub` | `PerspectiveHub(server: perspective.Server \| None = None)` | REQ-SRV-001 |
| `get_hub` | `get_hub() -> PerspectiveHub` (hub del proceso, perezoso) | REQ-SRV-001 |
| `perspective_api` | `perspective_api(path=DEFAULT_PATH, hub=None, executor=None, allowed_origins=None, *, authorize=None, read_only=False, write_close_code=4409, read_variants=None, max_sessions=None, on_reject=None) -> Starlette` | REQ-SRV-002/003/017 |
| `mount` | `mount(app, path=DEFAULT_PATH, hub=None, executor=None, allowed_origins=None, *, …mismos…) -> PerspectiveHub` | REQ-SRV-005/017 |
| `origin_allowed` | `origin_allowed(origin: str \| None, allowed: Sequence[str]) -> bool` | REQ-SRV-003 |
| `run_periodically` | `run_periodically(func, interval: float) -> Callable` | REQ-SRV-006 |
| `request_variant` | `request_variant(payload: bytes) -> int \| None` | REQ-SRV-013/014 |
| `is_read_request` | `is_read_request(payload: bytes, read_variants: Collection[int] \| None = None) -> bool` | REQ-SRV-013 |
| `READ_VARIANTS` | `Mapping[str, frozenset[int]]` (lecturas verificadas por versión, §2.2) | REQ-SRV-013, REQ-VER-003 |
| `WRITE_VARIANT_NAMES` | `Mapping[int, str]` (escrituras conocidas, para logs) | REQ-SRV-014 |
| `WRITE_CLOSE_CODE` | `4409` | REQ-SRV-014 |

`request_variant` devuelve el número de la única variante del `oneof` o `None` si el frame es
ilegible o trae más de una; `is_read_request` usa por omisión la tabla de la versión instalada
(y lanza `RuntimeError` si no la hay). Son públicos para que una app que componga su propio
handler (p. ej. con tope de sesiones) no copie el clasificador.

Opciones de acceso (sólo por palabra clave en `serve()`, `asgi_app()`, `perspective_api()` y
`mount()`, REQ-SRV-017):

```python
Authorize = Callable[[WebSocket], Awaitable[int | None] | int | None]
OnReject = Callable[[int, WebSocket], Awaitable[None] | None]

async def PerspectiveHub.serve(
    websocket, executor=None, allowed_origins=None, *,
    authorize: Authorize | None = None,
    read_only: bool = False,
    write_close_code: int = 4409,
    read_variants: Collection[int] | None = None,
    max_sessions: int | None = None,
    on_reject: OnReject | None = None,
) -> None
```

`authorize` y `on_reject` pueden ser síncronos o asíncronos. `on_reject(code, websocket)` se
llama antes de cada cierre de rechazo (REQ-SRV-020); sus errores se registran y no cambian el
cierre (REQ-SRV-021). `max_sessions` cuenta todas las sesiones del hub (REQ-SRV-019). Al
construir la app: `ValueError` si `write_close_code` está fuera de 4000–4999 (REQ-SRV-018) o
`max_sessions` no es un entero ≥ 1 (REQ-SRV-023); `RuntimeError` si `read_only=True` sin
`read_variants` en una versión sin tabla verificada (REQ-SRV-015).

### 1.1 `PerspectiveHub`

| Método | Comportamiento |
|---|---|
| `table(data, name, *, index=None, limit=None, replace=False)` | Crea la tabla o devuelve la existente; con `replace=True` reemplaza sus filas |
| `get_table(name)` | Handle de la tabla; `KeyError` si no existe (REQ-SRV-007) |
| `has_table(name)` / `table_names()` | Consulta de tablas hospedadas |
| `delete_table(name)` | Borra (perezoso) |
| `update(name, data, **kw)` / `remove(name, keys)` / `clear(name)` | Escrituras desde Python |
| `size(name)` / `query(name, **view_config)` | Lecturas desde Python |
| `session_count` (propiedad) | Sesiones WebSocket abiertas en el hub (REQ-SRV-022) |
| `serve(websocket, executor=None, allowed_origins=None, *, authorize=None, read_only=False, write_close_code=4409, read_variants=None)` | Sesión WebSocket (§2) |
| `asgi_app(path=DEFAULT_PATH, executor=None, allowed_origins=None, *, …mismas opciones…)` | `Starlette` con la ruta WebSocket |

`allowed_origins=None` usa `cors_allowed_origins` de Reflex (o `("*",)` sin `rxconfig.py`);
`"*"` en la lista admite cualquier origen.

## 2. Protocolo del WebSocket

- Transporte: frames **binarios**; cada uno es un mensaje `perspective.proto` (`Request` del
  cliente, `Response` del servidor) de la versión `PERSPECTIVE_VERSION`.
- Frames vacíos o de texto: se descartan (REQ-SRV-004).
- Orden: las peticiones de una sesión se ejecutan de a una, en orden de llegada.
- Controles, en orden (DD-005, DD-009): `Origin` → `authorize` → tope de sesiones → `accept()` → sesión → por frame:
  descartar vacío/texto → clasificar si `read_only` → executor.

### 2.1 Códigos de cierre

| Código | Cuándo | Antes/después de `accept()` |
|---|---|---|
| 1008 | `Origin` no permitido (REQ-SRV-003) | Antes (en un servidor ASGI real el cliente ve un rechazo HTTP 403 del handshake) |
| código de `authorize` (4000–4999 o 1008) | Autorización denegada (REQ-SRV-011) | Después, sin sesión |
| 1011 | `authorize` falló o devolvió un código inválido (REQ-SRV-012) | Después, sin sesión |
| `write_close_code` (4409) | Frame no permitido en sólo lectura (REQ-SRV-014) | Con sesión; se cierra |
| 4429 | Tope de sesiones alcanzado (REQ-SRV-019); el visor lo trata como transitorio y reintenta | Después, sin sesión |
| 1000/1001 | Cierre normal del cliente | — |

Por omisión no hay autenticación ni control de escrituras (compatibilidad con 0.1.0); se
activan con `authorize` y `read_only=True`.

### 2.2 Variantes de `Request` en Perspective 5.5.1

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
cliente oficial y con un pase en navegador sobre la demo el 2026-10-03.
`tests/test_specs.py` comprueba que esta tabla es la del código.

## 3. Componente: props de modo servidor

| Prop | Tipo | Descripción |
|---|---|---|
| `server_url` | `str` | Ruta (relativa al backend de Reflex) o URL `ws://` absoluta |
| `server_table` | `str` | Nombre de la tabla hospedada |
| `server_mode` | `"server" \| "replicated"` | Virtual (por omisión) o réplica en el navegador |
| `on_disconnect` | evento `(url, code)` | Conexión perdida; `code` es el código de cierre o `None`. Ante 4400–4499 salvo 4429 el visor no reintenta esa URL hasta recargar (REQ-VIEW-011/012) |

Escrituras del navegador sobre una tabla de servidor (`update_rows`, `remove_keys`,
`rp.update`, `rp.remove`, `rp.replace`, `rp.clear`, `edit_mode="EDIT"`) viajan por el
WebSocket como peticiones de escritura del protocolo. En modo `replicated` escriben sólo en la
réplica local.
