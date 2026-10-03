# Analyze — WebSocket con autorización y en sólo lectura · 2026-10-03

Lectura cruzada de `proposal.md`, `delta-spec.md`, `tasks.md`, las specs base de `specs/`, el
borrador original de la consola y el código de `server.py` / `perspective_viewer.jsx`.

## Hallazgos sobre el borrador original (ya corregidos en este delta)

| # | Severidad | Categoría | Hallazgo | Resolución |
|---|---|---|---|---|
| A-01 | CRÍTICO | No felices | Clasificar por el primer campo del `oneof` deja pasar un frame `lectura + escritura` (protobuf: gana el último). Reproducido con 5.5.1. **El handler actual de la consola (`cs_soporte/analitica/hub.py`, `variante()`) tiene este hueco.** | DD-007, REQ-SRV-013/014, `test_read_only_rejects_smuggled_write` |
| A-02 | ALTO | Constitución (Art. 5) | `_es_escritura` (lista de escrituras) deja pasar variantes nuevas o renumeradas; en `master` ya cambia el campo 9 → 41 | Lista de lecturas por versión (DD-008) |
| A-03 | ALTO | Ambigüedad | "`authorize` antes de `accept()` y cierra con ese código": en ASGI real el código no llega al navegador si no se acepta | DD-006, REQ-SRV-011 |
| A-04 | ALTO | Cobertura | El borrador no define qué pasa si `authorize` lanza una excepción ni con códigos inválidos | REQ-SRV-012, REQ-SRV-018 |
| A-05 | MEDIO | Cobertura | Lecturas legítimas no listadas en la consola: 23, 39, 40 | Tabla §2.2 del delta |
| A-06 | MEDIO | No felices | Sin regla para la versión de Perspective sin tabla verificada | REQ-SRV-015 |
| A-07 | MEDIO | Terminología | Borrador en español con identificadores en español (`_es_escritura`) en una librería con API en inglés | API pública en inglés (`is_read_request`, `request_variant`) |

## Hallazgos abiertos

| # | Severidad | Categoría | Hallazgo | Artefactos | Sugerencia |
|---|---|---|---|---|---|
| A-08 | MEDIO | No felices | El puente reintenta indefinidamente ante 4401/4403/4409 (cada ≤10 s) y `on_disconnect` no recibe el código | PRD REQ-VIEW-010, proposal P-02 | Cambio aparte: envolver el WebSocket del cliente para leer `CloseEvent.code` y no reintentar 4400–4499 |
| A-09 | MEDIO | No felices | `read_only` + visor de servidor con `edit_mode="EDIT"`/`update_rows`/`rp.update` cierra el socket y el puente reconecta: bucle visible al usuario | delta MODIFIED README, A-08 | Documentado; un aviso en consola del navegador sería mejor (con A-08) |
| A-10 | BAJO | Ambigüedad | Las pruebas de T-004 requieren un `perspective.Client` que escriba en el `TestClient`; el patrón no está en el repo | tasks T-004 | Resolver en T-001 con un helper de prueba compartido |
| A-11 | BAJO | Cobertura | Métricas de rechazos (la consola cuenta por código) | proposal P-03 | Diferido; el logger da el dato |
| A-12 | BAJO | Datos | `view_to_*` permite exportar todo lo que el usuario ve; `read_only` no lo impide | PRD §6 MODIFIED | Documentado como fuera de alcance |

Cobertura: los 10 REQ nuevos tienen ≥1 tarea y ≥1 test nombrado; no hay tareas huérfanas
(T-008/T-009 citan Art. 7 y la publicación). Dependencias sin ciclos; [P] sólo entre tareas sin
archivos en común salvo `tests/test_server.py` en T-002/T-003, que tocan funciones distintas.

**Veredicto: LISTO PARA IMPLEMENTAR** (sin críticos abiertos). Primera tanda: T-001…T-004.

> Nota fuera de este repo: A-01 y A-05 afectan **hoy** al handler de la consola de CuidaSalud.
> Conviene corregirlo allí sin esperar a la 0.2.0.
