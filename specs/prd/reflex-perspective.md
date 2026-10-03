# PRD — reflex-perspective

> Versión de la spec: 1.1 (librería `0.2.0`) · Fecha: 2026-10-03
> Autor: Ernesto Crespo (mantenedor) · Estado: vigente (1.0 reconstruida del código; 1.1 pliega
> `2026-10-ws-authorize-read-only` y `2026-10-perspective-version-guard`)

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

### 4.3 Versiones (REQ-VER)

- **REQ-VER-001**: EL SISTEMA DEBERÁ fijar los paquetes npm `@perspective-dev/*` a
  `PERSPECTIVE_VERSION` y `perspective-python` a la misma versión en los extras.
- **REQ-VER-002**: EL SISTEMA DEBERÁ funcionar en modo cliente con Python ≥ 3.10 y en modo
  servidor con Python ≥ 3.11.
- **REQ-VER-003** (ubicuo): EL SISTEMA DEBERÁ incluir una prueba de contrato que genere cada
  operación de lectura y de escritura con el cliente oficial de la versión pineada, compruebe
  su variante contra la tabla y falle si `PERSPECTIVE_VERSION` no tiene tabla.
- **REQ-VER-004** (no deseado): SI `perspective-python` en los extras `server` o `dev` de
  `pyproject.toml` difiere de `PERSPECTIVE_VERSION`, ENTONCES el workflow **Quality** DEBERÁ
  fallar con un error que nombre las tres versiones.
- **REQ-VER-005** (ubicuo): Dependabot NO DEBERÁ proponer actualizaciones de
  `perspective-python`; la subida sigue `specs/runbooks/perspective-upgrade.md`.

## 5. Requisitos no funcionales

- Un pivote sobre una tabla grande no bloquea el lazo de eventos de Reflex (Art. 6).
- Compatibilidad hacia atrás en cada versión `0.x` salvo sección Breaking (Art. 4).

## 6. Limitaciones conocidas (0.2.0)

- **Por omisión el WebSocket no autentica y es escribible** (compatibilidad con 0.1.0, Art. 4);
  `authorize` y `read_only=True` lo cierran (REQ-SRV-010…018). `read_only` no impide exportar
  lo que el usuario puede ver (las lecturas `view_to_*` siguen permitidas).
- Cada worker del backend tiene su propio hub.
- El puente no distingue el código de cierre del WebSocket: todo cierre se reintenta, también
  4401/4403/4409 (fase 9a del plan).

## Constitution check

Art. 2 y 3 se verifican con `tests/test_server.py` / `tests/test_viewer.py`,
`tests/test_versions.py` y la prueba de contrato (REQ-VER-003/004); Art. 6 con REQ-SRV-002;
Art. 5 con el clasificador por lista de permitidos (REQ-SRV-013/014) y la guardia de versión
(REQ-SRV-015).
