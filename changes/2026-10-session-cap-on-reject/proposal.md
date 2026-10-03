# Propuesta — Tope de sesiones y gancho de rechazos

> Estado: **aprobada** (Ernesto Crespo, 2026-10-03) · Fecha: 2026-10-03 · Autor: Ernesto Crespo (mantenedor)
> Origen: P-03 y A-11 de [`_archivo/2026-10-ws-authorize-read-only/`](../_archivo/2026-10-ws-authorize-read-only/)
> Specs base afectadas: `specs/prd/reflex-perspective.md` §4.2, `specs/api/server-api-v1.md` §1–2,
> `specs/technical/server-architecture.md` §3–4
> Versión objetivo: **0.3.0**

## Problema

La consola de CuidaSalud mantiene en su código un tope de sesiones (cierra con 4429) y cuenta los
rechazos por código para sus métricas. Con 0.2.0 puede delegar `authorize` y `read_only` en la
librería, pero sigue envolviendo `hub.serve()` para el tope, y sólo puede contar rechazos leyendo
el logger (A-11), lo que ata sus métricas al texto de los mensajes.

## Alcance

- `max_sessions: int | None = None`: si el hub ya tiene ese número de sesiones WebSocket
  abiertas, la conexión nueva se acepta y se cierra con **4429** sin crear sesión (mismo motivo
  que DD-006). Se evalúa después de `Origin` y `authorize`.
- `on_reject: Callable[[int, WebSocket], None | Awaitable[None]] | None = None`: se llama en cada
  rechazo con su código (1008 `Origin`, código de `authorize`, 1011, `write_close_code`, 4429).
  Una excepción del gancho se registra y no cambia el cierre.
- `PerspectiveHub.session_count`: sesiones WebSocket abiertas en el hub.
- Ambos parámetros sólo por palabra clave en `serve()`, `asgi_app()`, `perspective_api()` y
  `mount()`; `ValueError` al construir si `max_sessions` no es un entero ≥ 1.

**Fuera de alcance**: tope por usuario o por tabla (la app lo hace en `authorize`); colas de
espera.

## Impacto

- Compatibilidad: hacia atrás; por omisión nada cambia (Art. 4).
- El puente (9a) trata 4429 como transitorio y sigue reintentando con espera exponencial.
- El tope cuenta todas las sesiones del hub, aunque tenga varias rutas montadas.

## Constitution check

Art. 4 (opcionales, valores por omisión de 0.2.0), Art. 5 (el gancho de métricas no puede
convertir un rechazo en aceptación: falla cerrado), Art. 6 (el contador se actualiza en el lazo
del socket, sin bloquear), Art. 2 (pruebas con el cliente oficial), Art. 7 (esta propuesta).
