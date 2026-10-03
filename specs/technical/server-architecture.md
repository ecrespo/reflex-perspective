# Diseño técnico — modo servidor de reflex-perspective

> Versión de la spec: 1.0 (librería `0.1.0`) · Fecha: 2026-10-03
> PRD §4.2 · API [`../api/server-api-v1.md`](../api/server-api-v1.md)

## 1. Contexto

```
navegador                           backend Reflex (un proceso)
<perspective-viewer>                 Starlette (api_transformer)
  @perspective-dev/client ──WS──▶   ruta /perspective → PerspectiveHub.serve()
                                        │ origin_allowed()            (REQ-SRV-003)
                                        │ server.new_session(send)
                                        │ loop.run_in_executor(handle_request)  (Art. 6)
                                        ▼
                                    perspective.Server  ◀── hub.update() desde handlers,
                                                            tareas de vida, hilos
```

## 2. Componentes

| Componente | Responsabilidad | No hace |
|---|---|---|
| `PerspectiveHub` | Servidor + cliente local, caché de handles, helpers de tablas | Persistir tablas |
| `serve()` | Origen, sesión, reenvío de frames al motor, cola de salida | Autenticar, filtrar escrituras (0.1.0) |
| `asgi_app` / `perspective_api` / `mount` | Exponer `serve()` como ruta Starlette en `api_transformer` | — |
| Puente JSX | `perspective.websocket(url)`, caché de clientes por URL, reintentos | Distinguir códigos de cierre |

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
npm y Python se fijan a la misma versión exacta (Art. 3).

## 4. Seguridad (estado 0.1.0)

| Amenaza | Mitigación actual | Hueco |
|---|---|---|
| Página ajena abre el socket | `Origin` (DD-003) | Por omisión Reflex permite `"*"` |
| Usuario sin sesión lee tablas | — | Sin gancho de autorización |
| Usuario con acceso modifica tablas (`update`, `remove`, `replace`/`clear`, `delete`, `make_table`, `make_join_table`) | — | Todo frame llega al motor |

Los huecos los cierra [`changes/2026-10-ws-authorize-read-only/`](../../changes/2026-10-ws-authorize-read-only/).

## 5. Límites

- Un hub por proceso: con varios workers cada uno tiene sus tablas.
- Un `perspective.Server` atiende los pivotes de una sesión de a uno; para muchas sesiones
  concurrentes, la app puede tener varios hubs (patrón usado en la consola de CuidaSalud).

## Constitution check

Art. 6 (DD-001, DD-002), Art. 3 (DD-004). Art. 5 incumplido en 0.1.0 para escrituras y
autenticación: excepción documentada en el README y propuesta abierta para resolverla.
