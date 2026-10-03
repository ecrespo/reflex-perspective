# API — `reflex_perspective.server` v1

> Versión de la spec: 1.0 (librería `0.1.0`) · Fecha: 2026-10-03
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
| `perspective_api` | `perspective_api(path=DEFAULT_PATH, hub=None, executor=None, allowed_origins=None) -> Starlette` | REQ-SRV-002/003 |
| `mount` | `mount(app, path=DEFAULT_PATH, hub=None, executor=None, allowed_origins=None) -> PerspectiveHub` | REQ-SRV-005 |
| `origin_allowed` | `origin_allowed(origin: str \| None, allowed: Sequence[str]) -> bool` | REQ-SRV-003 |
| `run_periodically` | `run_periodically(func, interval: float) -> Callable` | REQ-SRV-006 |

### 1.1 `PerspectiveHub`

| Método | Comportamiento |
|---|---|
| `table(data, name, *, index=None, limit=None, replace=False)` | Crea la tabla o devuelve la existente; con `replace=True` reemplaza sus filas |
| `get_table(name)` | Handle de la tabla; `KeyError` si no existe (REQ-SRV-007) |
| `has_table(name)` / `table_names()` | Consulta de tablas hospedadas |
| `delete_table(name)` | Borra (perezoso) |
| `update(name, data, **kw)` / `remove(name, keys)` / `clear(name)` | Escrituras desde Python |
| `size(name)` / `query(name, **view_config)` | Lecturas desde Python |
| `serve(websocket, executor=None, allowed_origins=None)` | Sesión WebSocket (§2) |
| `asgi_app(path=DEFAULT_PATH, executor=None, allowed_origins=None)` | `Starlette` con la ruta WebSocket |

`allowed_origins=None` usa `cors_allowed_origins` de Reflex (o `("*",)` sin `rxconfig.py`);
`"*"` en la lista admite cualquier origen.

## 2. Protocolo del WebSocket

- Transporte: frames **binarios**; cada uno es un mensaje `perspective.proto` (`Request` del
  cliente, `Response` del servidor) de la versión `PERSPECTIVE_VERSION`.
- Frames vacíos o de texto: se descartan (REQ-SRV-004).
- Orden: las peticiones de una sesión se ejecutan de a una, en orden de llegada.

### 2.1 Códigos de cierre

| Código | Cuándo | Antes/después de `accept()` |
|---|---|---|
| 1008 | `Origin` no permitido (REQ-SRV-003) | Antes (en un servidor ASGI real el cliente ve un rechazo HTTP 403 del handshake) |
| 1000/1001 | Cierre normal del cliente | — |

No hay autenticación ni control de escrituras en esta versión (ver PRD §6).

## 3. Componente: props de modo servidor

| Prop | Tipo | Descripción |
|---|---|---|
| `server_url` | `str` | Ruta (relativa al backend de Reflex) o URL `ws://` absoluta |
| `server_table` | `str` | Nombre de la tabla hospedada |
| `server_mode` | `"server" \| "replicated"` | Virtual (por omisión) o réplica en el navegador |

Escrituras del navegador sobre una tabla de servidor (`update_rows`, `remove_keys`,
`rp.update`, `rp.remove`, `rp.replace`, `rp.clear`, `edit_mode="EDIT"`) viajan por el
WebSocket como peticiones de escritura del protocolo. En modo `replicated` escriben sólo en la
réplica local.
