# PRD — reflex-perspective

> Versión de la spec: 1.0 (línea base de la librería `0.1.0`) · Fecha: 2026-10-03
> Autor: Ernesto Crespo (mantenedor) · Estado: línea base, reconstruida del código

## 1. Problema

Las apps Reflex que necesitan explorar datasets grandes o en streaming (pivotes, filtros,
gráficos WebGL) no tienen un componente que lo haga sin pasar los datos por el estado de
Reflex. Perspective (motor WebAssembly + `<perspective-viewer>`) lo resuelve, pero integrarlo
exige un puente React, el arranque de WASM compatible con SSR y, para el modo servidor, un
WebSocket dentro del backend de Reflex.

## 2. Usuarios

- **Desarrollador Reflex** que añade un visor analítico a su app (modo cliente).
- **Desarrollador de backend** que hospeda tablas en Python y las sirve a muchos visores
  (modo servidor / replicado). Ejemplo real: el panel de análisis de la consola de soporte de
  CuidaSalud (modo servidor, varios usuarios, datos de producción).

## 3. Alcance

Dentro: componente `perspective_viewer`, acciones imperativas, eventos, workspaces, módulo
`reflex_perspective.server` (hub + WebSocket), demo.
Fuera: autenticación de usuarios (la aporta la app), persistencia de tablas, varios workers
compartiendo un hub.

## 4. Requisitos

Notación EARS. MUST salvo que se indique.

### 4.1 Visor (REQ-VIEW)

- **REQ-VIEW-001**: EL SISTEMA DEBERÁ soportar las tres arquitecturas de datos de Perspective:
  sólo cliente (`data`, `schema`, `url`), sólo servidor (`server_url` + `server_table`) y
  replicada (`server_mode="replicated"`).
- **REQ-VIEW-002**: CUANDO cambie una prop de configuración (`plugin`, `group_by`, `columns`,
  …), EL SISTEMA DEBERÁ aplicar sólo la diferencia con `restore()`, sin recrear la tabla.
- **REQ-VIEW-003**: CUANDO cambie `data` en modo cliente, EL SISTEMA DEBERÁ llamar
  `table.replace()` conservando la vista del usuario.
- **REQ-VIEW-004**: CUANDO cambien `update_rows` o `remove_keys`, EL SISTEMA DEBERÁ aplicarlos
  con `table.update()` / `table.remove()` sobre la tabla del visor.
- **REQ-VIEW-005**: EL SISTEMA DEBERÁ exponer los Custom Events de Perspective como eventos
  Reflex (`on_load`, `on_click`, `on_select`, `on_config_update`, `on_global_filter_update`,
  `on_layout_update`, `on_active_panel_update`, `on_toggle_settings`, `on_disconnect`,
  `on_error`).
- **REQ-VIEW-006**: SI el visor emite una config y la app la devuelve por `config`
  (lazo controlado), ENTONCES EL SISTEMA NO DEBERÁ re-aplicarla.
- **REQ-VIEW-007**: EL SISTEMA DEBERÁ exponer acciones imperativas como `EventSpec`
  (`save`, `restore`, `download`, `export`, `update`, `remove`, `replace`, `clear`, …).
- **REQ-VIEW-008**: EL SISTEMA DEBERÁ soportar workspaces multi-panel con paneles maestros y
  filtros globales.
- **REQ-VIEW-009**: EL SISTEMA DEBERÁ cargar WASM de forma perezosa y segura con SSR.
- **REQ-VIEW-010**: SI se pierde la conexión del WebSocket en modo servidor, ENTONCES EL
  SISTEMA DEBERÁ emitir `on_disconnect` y reintentar con espera exponencial (500 ms × 2ⁿ,
  tope 10 s).

### 4.2 Modo servidor (REQ-SRV)

- **REQ-SRV-001**: EL SISTEMA DEBERÁ ofrecer un `PerspectiveHub` seguro entre hilos para
  crear, abrir, actualizar, borrar y consultar tablas hospedadas por nombre.
- **REQ-SRV-002**: EL SISTEMA DEBERÁ servir una sesión de Perspective por WebSocket en la ruta
  configurada (por omisión `/perspective`) y ejecutar cada petición al motor en un executor,
  de a una por sesión y en orden.
- **REQ-SRV-003**: SI el `Origin` del handshake no está en los orígenes permitidos (por
  omisión `cors_allowed_origins` de Reflex), ENTONCES EL SISTEMA DEBERÁ cerrar con 1008 sin
  aceptar el socket. Un handshake sin `Origin` (cliente no navegador) se acepta.
- **REQ-SRV-004**: SI llega un frame vacío o de texto, ENTONCES EL SISTEMA DEBERÁ descartarlo
  sin reenviarlo al motor.
- **REQ-SRV-005**: CUANDO se llame `mount(app, …)`, EL SISTEMA DEBERÁ conservar cualquier
  `api_transformer` existente y añadir el suyo.
- **REQ-SRV-006**: EL SISTEMA DEBERÁ ofrecer `run_periodically(func, interval)` como tarea de
  vida de Reflex que sobrevive a excepciones de `func`.
- **REQ-SRV-007**: SI una tabla cacheada fue borrada por otro cliente, ENTONCES EL SISTEMA
  DEBERÁ descartar el handle y tratarla como inexistente.

### 4.3 Versiones (REQ-VER)

- **REQ-VER-001**: EL SISTEMA DEBERÁ fijar los paquetes npm `@perspective-dev/*` a
  `PERSPECTIVE_VERSION` y `perspective-python` a la misma versión en los extras.
- **REQ-VER-002**: EL SISTEMA DEBERÁ funcionar en modo cliente con Python ≥ 3.10 y en modo
  servidor con Python ≥ 3.11.

## 5. Requisitos no funcionales

- Un pivote sobre una tabla grande no bloquea el lazo de eventos de Reflex (Art. 6).
- Compatibilidad hacia atrás en cada versión `0.x` salvo sección Breaking (Art. 4).

## 6. Limitaciones conocidas (línea base 0.1.0)

- **El WebSocket no autentica y es escribible**: cualquier cliente que lo alcance puede leer y
  modificar cada tabla hospedada. Lo aborda
  [`changes/2026-10-ws-authorize-read-only/`](../../changes/2026-10-ws-authorize-read-only/).
- Cada worker del backend tiene su propio hub.
- El puente no distingue el código de cierre del WebSocket: todo cierre se reintenta.

## Constitution check

Art. 2 y 3 se verifican con `tests/test_server.py` / `tests/test_viewer.py` y el pin de
versiones; Art. 6 con REQ-SRV-002. La limitación de seguridad (Art. 5) queda abierta como
cambio propuesto.
