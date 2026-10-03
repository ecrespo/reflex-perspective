# Propuesta — Códigos de cierre en el puente del visor

> Estado: **aprobada** (Ernesto Crespo, 2026-10-03) · Fecha: 2026-10-03 · Autor: Ernesto Crespo (mantenedor)
> Origen: P-02 y hallazgos A-08 / A-09 de [`_archivo/2026-10-ws-authorize-read-only/`](../_archivo/2026-10-ws-authorize-read-only/)
> Specs base afectadas: `specs/prd/reflex-perspective.md` §4.1 (REQ-VIEW-005, REQ-VIEW-010) y §6,
> `specs/runbooks/perspective-upgrade.md`
> Versión objetivo: **0.3.0**

## Problema

Desde 0.2.0 el servidor cierra con códigos que significan "no reintentes": 4401/4403 (los de
`authorize`) y 4409 (escritura en sólo lectura). El puente JSX trata todo cierre igual y
reintenta cada ≤10 s para siempre: un bucle inútil para el usuario, más carga en el servidor y
logs llenos de rechazos. Además `on_disconnect` sólo recibe la URL, así que la app no puede
distinguir "el backend se reinició" de "no tienes permiso" (A-08). Un visor de servidor con
`edit_mode="EDIT"` contra un socket de sólo lectura se desconecta y reconecta sin explicación
(A-09).

## Alcance

- El puente obtiene el código de cierre del error que el cliente de Perspective entrega a
  `on_error` (el transporte oficial lo formatea como `WebSocket closed <código>`).
- Ante 4400–4499, **salvo 4429** ("demasiadas sesiones, vuelve luego"), no se reintenta esa URL
  hasta recargar la página; todos los visores de esa URL dejan de reintentar (comparten socket).
- Aviso en la consola del navegador con el código y su causa probable (4401, 4403, 4409, otros).
- `on_disconnect` recibe `(url, code)`; `code` es `None` si no se conoce. Los handlers de un
  solo argumento siguen funcionando (Reflex admite ambas firmas).
- Pruebas JS de las funciones puras del puente con `esbuild` (ya usado en CI) y `node --test`,
  lanzadas desde pytest; se omiten si no hay `node`/`npx`.

**Fuera de alcance**: reintentos configurables; distinguir el 1006 de un `Origin` rechazado
(el navegador no recibe el código, ver API §2.1).

## Factibilidad (2026-10-03)

| Punto | Resultado |
|---|---|
| ¿Se puede leer `CloseEvent.code`? | No directamente: `perspective.websocket()` crea el socket por dentro y el build de navegador no exporta `Client` para montar un transporte propio. Pero `websocket.ts` (5.5.1) llama `client.handle_error("WebSocket closed " + event.code, connect)`, y `Client.on_error(cb)` invoca `cb(error, reconnect)`. |
| Riesgo de formato | El texto es de la versión pineada. Se añade un paso al runbook de subida y el pase en navegador lo comprueba; si el formato cambiara, el código sería `None` y el puente vuelve al comportamiento de 0.2.0 (reintentar): falla hacia la disponibilidad, no abre nada. |
| Firma del evento | Probado con Reflex 0.9.12: `EventHandler[_url_code_spec, _str_spec]` acepta handlers de 1 y 2 argumentos. |

## Impacto

- Compatibilidad: hacia atrás (Art. 4). Cambia el comportamiento sólo ante cierres 44xx, que en
  0.2.0 producían un bucle.
- Consumidores: la consola de CuidaSalud deja de ver reintentos tras 4401/4403 y puede mostrar
  un mensaje según `code`.

## Constitution check

Art. 4 (handlers de un argumento intactos; sin parámetros obligatorios nuevos), Art. 2 (las
funciones del puente se prueban; el pase en navegador cubre la integración), Art. 3 (formato del
mensaje atado a la versión y al runbook), Art. 7 (esta propuesta).
