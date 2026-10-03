# Diseño técnico — modo servidor de reflex-perspective

> Versión de la spec: 1.2 (librería `0.3.0`) · Fecha: 2026-10-03
> PRD §4.2 · API [`../api/server-api-v1.md`](../api/server-api-v1.md)

## 1. Contexto

```
navegador                           backend Reflex (un proceso)
<perspective-viewer>                 Starlette (api_transformer)
  @perspective-dev/client ──WS──▶   ruta /perspective → PerspectiveHub.serve()
                                        │ origin_allowed()            (REQ-SRV-003)
                                        │ authorize(websocket)        (REQ-SRV-010…012)
                                        │ tope max_sessions → 4429    (REQ-SRV-019)
                                        │ on_reject(code, ws) en cada rechazo (REQ-SRV-020)
                                        │ server.new_session(send)
                                        │ is_read_request() si read_only (REQ-SRV-013/014)
                                        │ loop.run_in_executor(handle_request)  (Art. 6)
                                        ▼
                                    perspective.Server  ◀── hub.update() desde handlers,
                                                            tareas de vida, hilos
```

## 2. Componentes

| Componente | Responsabilidad | No hace |
|---|---|---|
| `PerspectiveHub` | Servidor + cliente local, caché de handles, helpers de tablas | Persistir tablas |
| `serve()` | Origen, `authorize`, tope de sesiones, `on_reject`, sesión, clasificación en sólo lectura, reenvío al motor, cola de salida | Autorización por tabla |
| Clasificador (`request_variant`, `is_read_request`, `READ_VARIANTS`) | Decidir si un frame es exactamente una lectura conocida de la versión pineada | Decodificar el protobuf completo |
| `asgi_app` / `perspective_api` / `mount` | Exponer `serve()` como ruta Starlette en `api_transformer` | — |
| Puente JSX | `perspective.websocket(url)`, caché de clientes por URL, reintentos; lee el código de cierre del error de `on_error` y no reintenta 4400–4499 salvo 4429 (DD-010) | Reintentos configurables |

## 3. Decisiones

### DD-001: Handler propio en vez de `PerspectiveStarletteHandler`
El handler de Perspective llama al socket desde el hilo que actualizó la tabla. `serve()`
encola cada mensaje saliente en el lazo dueño del socket (`call_soon_threadsafe`), así que
las tablas se pueden actualizar desde cualquier hilo.

### DD-002: Peticiones en executor
`session.handle_request` corre en `run_in_executor` (por omisión, el pool del lazo; o el
`executor` del usuario). Se esperan de a una para conservar el orden.

### DD-003: Control de `Origin` por omisión
Los navegadores no aplican CORS a los WebSockets. Sin este control cualquier página podría
abrir el endpoint (cross-site WebSocket hijacking). Se reutiliza `cors_allowed_origins`.

### DD-004: Versiones en bloque
El protocolo protobuf cambia entre versiones de Perspective sin compatibilidad garantizada.
npm y Python se fijan a la misma versión exacta (Art. 3). CI lo verifica
(`scripts/check_perspective_versions.py`, REQ-VER-004) y Dependabot no sube
`perspective-python` por separado (REQ-VER-005).

### DD-005: Orden de controles en `serve()`
`Origin` (1008, sin aceptar) → `authorize` (sin sesión) → `accept()` → si hubo código, cerrar
con él → crear sesión → por frame: descartar vacío/texto (REQ-SRV-004) → clasificar si
`read_only` → executor. La sesión de Perspective nunca existe para una conexión rechazada.

### DD-006: Aceptar y cerrar para entregar el código de `authorize`
En un servidor ASGI real (uvicorn/granian), cerrar antes de `accept()` rechaza el handshake con
HTTP 403 y el navegador ve 1006: el código se pierde. Para que la app distinga "sin sesión"
de "sin permiso", se acepta y se cierra en el acto. Alternativa descartada: la extensión
`websocket.http.response` (respuesta HTTP de denegación), porque no todos los servidores la
implementan y el cliente de Perspective tampoco expone el estado HTTP.

### DD-007: Clasificador estricto por lista de permitidos
Se recorren **todas** las etiquetas de nivel superior del frame (varints protobuf; tipos
0, 1, 2, 5). Se exige un único campo distinto de `msg_id` (1) y `entity_id` (2), y que sea de
longitud delimitada (un mensaje); cualquier segundo campo, tipo de cable desconocido, campo 0,
longitud que sobrepase el frame o varint truncado → ilegible → rechazo. Motivo: en un `oneof`
protobuf gana el último campo, así que mirar sólo el primero permite anteponer una lectura a
una escritura (reproducido con 5.5.1 concatenando dos frames reales del cliente oficial). Se
descarta decodificar con el `.proto` compilado: añade una dependencia y la librería no publica
su esquema en Python.

### DD-008: Tabla de lecturas por versión, fallar cerrado
`READ_VARIANTS` se indexa por versión exacta (`"5.5.1"`). La versión se lee con
`importlib.metadata.version("perspective-python")`. Sin tabla para la versión instalada,
`read_only=True` no arranca (REQ-SRV-015) salvo `read_variants` explícito. Así una subida de
Perspective nunca deja el modo sólo lectura funcionando con números de otra versión.

### DD-009: Tope y métricas dentro de `serve()`
Orden: `Origin` → `authorize` → tope → `accept()` → sesión. El contador vive en el hub (protegido
por su lock), se incrementa al admitir y se libera en el `finally` de la sesión. `on_reject` se
llama justo antes de cada cierre de rechazo; sus errores se registran y nunca cambian el código
ni reabren la conexión.

### DD-010: Código de cierre en el puente a partir de `on_error`
`perspective.websocket()` crea el socket por dentro y el build de navegador no exporta `Client`
para montar un transporte propio. El transporte oficial informa el cierre a `Client.on_error`
con el texto `WebSocket closed <código>` (5.5.1); el puente lo extrae (`closeCodeFromError`).
Ante 4400–4499 salvo 4429 registra la URL como rechazada, avisa una vez en consola y bloquea los
reintentos de todos los visores de esa URL hasta recargar. Alternativa descartada: sustituir
`window.WebSocket`, que afectaría a todos los sockets de la página (incluido el de Reflex).

## 4. Seguridad (estado 0.3.0)

| Amenaza | Mitigación | Hueco restante |
|---|---|---|
| Página ajena abre el socket | `Origin` (DD-003) | Por omisión Reflex permite `"*"` |
| Usuario sin sesión lee tablas | `authorize` (DD-005/006) cuando la app lo pasa | Por omisión sigue abierto (Art. 4); sin autorización por tabla |
| Usuario con acceso modifica tablas (`update`, `remove`, `replace`/`clear`, `delete`, `make_table`, `make_join_table`) | `read_only=True` (DD-007/008) | Por omisión sigue abierto (Art. 4) |
| Frame manipulado que esconde una escritura tras una lectura | Clasificador de un único campo (DD-007) | — |
| Subida de Perspective con variantes renumeradas o nuevas | Tabla por versión, prueba de contrato, fallar cerrado (DD-008) | — |
| Usuario exporta lo que ve (`view_to_*`) | — | Fuera de alcance: son lecturas |
| Exceso de sesiones agota el servidor | `max_sessions` (DD-009) cuando la app lo pasa | Por omisión sin tope; tope por proceso |
| Reintentos en bucle tras un rechazo | Puente sin reintentos ante 44xx salvo 4429 (DD-010) | — |

El README advierte que los dos controles se activan juntos en despliegues con más de un
usuario.

## 5. Límites

- Un hub por proceso: con varios workers cada uno tiene sus tablas.
- Un `perspective.Server` atiende los pivotes de una sesión de a uno; para muchas sesiones
  concurrentes, la app puede tener varios hubs (patrón usado en la consola de CuidaSalud).

## Constitution check

Art. 6 (DD-001, DD-002), Art. 3 (DD-004, DD-008), Art. 5 (DD-007, DD-008: lista de
permitidos y versión no verificada = no arranca). Los valores por omisión conservan el
comportamiento de 0.1.0 (Art. 4) y el README lo advierte.
