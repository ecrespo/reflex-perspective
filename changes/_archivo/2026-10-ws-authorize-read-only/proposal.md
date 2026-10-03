# Propuesta — WebSocket con autorización y en sólo lectura

> Estado: **implementada** (0.2.0, 2026-10-03; aprobada por Ernesto Crespo el 2026-10-03) · Fecha: 2026-10-03 · Autor: Ernesto Crespo (mantenedor)
> Origen: `backoffice_CuidaSalud/docs/cuidasalud-soporte-specs/changes/2026-10-reflex-perspective-solo-lectura/` (borrador 2026-10-02, DD-017 de la consola)
> Specs base afectadas: `specs/prd/reflex-perspective.md` §4.2 y §6,
> `specs/api/server-api-v1.md` §1–2, `specs/technical/server-architecture.md` §2–4
> Versión objetivo: **0.2.0**

## Problema

`PerspectiveHub.serve()` acepta cualquier WebSocket cuyo `Origin` esté permitido y pasa
**todos** los frames del cliente a `session.handle_request`, incluidos los que modifican
tablas. El README lo admite: "Any client that can reach it can read **and modify** every hosted
table". La autenticación queda en manos de un middleware externo sin punto de enganche claro.

El primer consumidor con varios usuarios (panel de análisis de la consola de CuidaSalud) tuvo
que copiar el handler entero (`cs_soporte/analitica/hub.py`) para añadir sesión, rol y sólo
lectura. Mantener ese clasificador fuera de la librería que fija la versión del protocolo es
frágil.

## Alcance

- `serve()`, `asgi_app()`, `perspective_api()` y `mount()` aceptan:
  - `authorize`: gancho llamado **antes de crear la sesión**; devuelve `None` (acepta) o un
    código de cierre.
  - `read_only: bool = False`: cada frame se clasifica antes de llegar al motor; lo que no es
    una lectura conocida cierra la conexión con `write_close_code` (4409 por omisión).
- Clasificador **estricto** por lista de permitidos, con tabla de variantes por versión de
  Perspective y prueba de contrato.
- README (nota de seguridad), `CHANGELOG.md` y publicación `0.2.0`.

**Fuera de alcance**: autorización por tabla; impedir exportar (las lecturas `view_to_*` siguen
permitidas); tope de sesiones y réplicas de hub (la consola los mantiene, ver P-03); cambios en
el puente JSX (ver P-02). Las escrituras desde Python (`hub.update`, tareas de vida) siguen
funcionando: el modo sólo lectura limita a los clientes del socket, no al servidor.

## Factibilidad (analizada el 2026-10-03)

**Factible, con tres correcciones al borrador original.** Evidencia reproducida con
`perspective-python` 5.5.1 y su cliente oficial en proceso:

| Punto | Resultado |
|---|---|
| ¿Se puede clasificar sin decodificar todo el protobuf? | Sí. El `Request` es `msg_id=1`, `entity_id=2` y un `oneof client_req`; basta recorrer las etiquetas de nivel superior (varints). Coste O(tamaño del frame), sin dependencias nuevas. |
| ¿Las variantes de 5.5.1 coinciden con el `.proto`? | Sí. Medidas con el cliente oficial: `get_hosted_tables`=4, `size`=8, `schema`=7, `validate_expressions`=9, `view`=6, `to_arrow`=16, `to_csv`=25, `on_update`=21, `on_remove`=39, `view.delete`=11; escrituras `update`=33, `remove`=31, `replace` y `clear`=32, `make_table`=27, `join`=38, `table.delete`=28. |
| **Corrección 1 — clasificar sólo el primer campo deja pasar escrituras** | Un frame `[1, 2, 8 (size), 33 (update)]` se clasifica como lectura si se mira sólo el primer campo del `oneof`, pero protobuf aplica "gana el último" y el motor **ejecuta el `update`** (reproducido: la tabla pasó de 4 a 5 filas). El clasificador debe exigir **exactamente un** campo fuera de {1, 2} y rechazar todo lo demás. Con esa regla el frame manipulado se rechaza y el tráfico legítimo pasa (prototipo verificado). |
| **Corrección 2 — lista de permitidos, no de escrituras** | El borrador nombra `_es_escritura` (lista de escrituras). En `master` de Perspective, posterior a 5.5.1, el campo 9 pasa a `reserved` y aparece el 41 `table_describe_req`: cualquier renumeración o variante nueva entraría como "no escritura". Se clasifica por **lecturas permitidas** (Art. 5). La consola ya llegó a la misma conclusión (DD-017 v1.6). |
| **Corrección 3 — el código de cierre no llega si se cierra antes de `accept()`** | En ASGI, cerrar antes de aceptar se traduce en un rechazo HTTP 403 del handshake; el navegador ve 1006, no 4401/4403. `authorize` se evalúa antes de crear la sesión, pero si devuelve un código el socket se **acepta y se cierra en seguida con ese código**, sin crear la sesión. (El `Origin` mantiene su comportamiento actual de cierre previo.) |
| Lecturas que el visor del navegador manda y "parecen" escrituras | `table_make_port` (5) al conectar y `remove_hosted_tables_update` (37) al desmontar (observadas por la consola en navegador). Ambas en la lista de permitidos. |
| Lecturas que faltan en el handler de la consola | 23 `view_set_depth`, 39 `view_on_remove`, 40 `view_remove_on_remove`. Se incluyen. |
| ¿Hay versión nueva de Perspective? | No: 5.5.1 (2026-09-18) es `latest` en npm y PyPI al 2026-10-03. Sí hay un cambio de protocolo sin publicar (9 → 41), que valida el diseño por versión y fallar cerrado. |
| Reflex | 0.9.12 sigue siendo la última; sin cambios. |

## Impacto

- **Compatibilidad**: hacia atrás. Parámetros opcionales; por omisión nada cambia (Art. 4).
- **Consumidores**: la consola de CuidaSalud puede retirar su handler propio y fijar
  `reflex-perspective[server]==0.2.0` (cierra su PR-11). Conserva su tope de vistas y sus
  réplicas, componiendo `hub.serve(...)` (ver P-03).
- **Incompatibilidades funcionales en `read_only=True`**: un visor de servidor con
  `edit_mode="EDIT"`, `update_rows`, `remove_keys` o las acciones `rp.update/remove/replace/clear`
  provoca el cierre 4409. Se documenta.
- **Riesgo**: que una versión nueva de Perspective use una variante de lectura no listada →
  el visor se desconecta (falla cerrado, no abre un hueco). Mitigación: tabla por versión,
  prueba de contrato y runbook de subida.

## Preguntas abiertas

- **P-01** ¿`read_only=True` con una versión de Perspective sin tabla verificada debe fallar al
  montar (`RuntimeError`) o permitir una tabla explícita `read_variants=`? Propuesta: ambas —
  falla al montar salvo que se pase `read_variants`.
- **P-02** El puente reintenta cualquier cierre cada ≤10 s. Con 4401/4403/4409 eso es un bucle
  inútil. `perspective.websocket()` no expone el código de cierre; resolverlo exige envolver el
  WebSocket en el puente. Se difiere a otro cambio.
- **P-03** ¿Subir a la librería el tope de sesiones (4429) y un gancho `on_reject(code)` para
  métricas, que la consola tiene hoy? Se difiere: con `authorize` la app puede implementar el
  tope; las métricas se pueden sacar del logger.

## Constitution check

- **Art. 5** (fallar cerrado): lista de permitidos, un único campo por frame, frame ilegible =
  rechazo, versión no verificada = no arranca.
- **Art. 4**: parámetros opcionales, valores por omisión idénticos a 0.1.0.
- **Art. 2**: pruebas con el cliente oficial; el frame manipulado es la única prueba con bytes a
  mano (permitida por el artículo).
- **Art. 3**: la tabla de variantes se ata a `PERSPECTIVE_VERSION`.
- **Art. 7**: el delta se pliega a `specs/` en el PR de la `0.2.0`.
