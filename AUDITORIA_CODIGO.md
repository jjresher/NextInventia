# Auditoría técnica de seguimiento — Patentólogos

**Fecha:** 14 de septiembre de 2026

**Rama revisada:** `develop`

**Commit:** `edd0b5b6c77910eebf758bae19f233aa79338b99`

**Alcance:** arquitectura, calidad, seguridad, privacidad, datos, rendimiento, pruebas y preparación operativa del frontend Next.js y el backend FastAPI.

**Naturaleza:** revisión estática y pruebas locales; no se modificó código ni se ejecutaron migraciones o servicios remotos.

## 1. Resumen ejecutivo

El proyecto mejoró de forma importante desde la auditoría del 2 de septiembre. El chat ya reconstruye el contexto desde IDs, los inputs costosos tienen límites en FastAPI, las dependencias Python son reproducibles, la búsqueda léxica está parametrizada, los errores públicos están redactados, existen timeouts, caché, contratos OpenAPI, observabilidad y CI. La base arquitectónica del MVP es ahora considerablemente más mantenible y verificable.

De los 33 hallazgos originales:

| Estado actual | Cantidad | Interpretación |
| --- | ---: | --- |
| Corregidos | 25 | La causa principal está resuelta y existe evidencia en código o pruebas. |
| Mitigado parcialmente | 1 | Hay controles, pero falta completar su activación en producción. |
| Pendientes | 7 | Siguen representados por los issues abiertos #12, #13, #14, #17, #24 y #25. |

El riesgo residual más importante no está en la organización del código, sino en publicar operaciones costosas sin identidad, cuotas y control global de concurrencia. También permanecen abiertos el acceso directo a RPC, el tratamiento de información enviada a Gemini y la reproducibilidad/seguridad del esquema de base de datos.

**Conclusión de despliegue:** el sistema está en buen estado para desarrollo local y pruebas controladas. Antes de abrirlo a usuarios reales en Internet conviene resolver, como mínimo, #12, #13, #14 y #17. #24 y #25 deben quedar resueltos antes de depender del entorno como un servicio recuperable y repetible.

## 2. Estado de los riesgos pendientes

### R-01 — Operaciones costosas públicas y sin control antiabuso distribuido

**Severidad:** alta · **Issues:** #12 y #13 · **Hallazgos originales:** A-02, M-05 y M-06

**Estado:** pendiente; el código confirma que el riesgo sigue vigente.

Las rutas de chat, búsqueda semántica y clasificación no exigen identidad ni aplican cuotas por usuario/IP (`backend/app/routes/chat.py:139`, `backend/app/routes/patents.py:31`, `backend/app/routes/classification.py:11`). Cada petición puede consumir Gemini, cargar/usar Sentence-BERT, consultar Supabase y recorrer el índice CPC.

El limitador de Gemini es seguro entre threads de un único proceso, pero su estado vive en memoria y no se comparte entre workers o réplicas (`backend/app/services/gemini_client.py`). Además, reserva cuota antes de la llamada y una petición fallida continúa contabilizada. No existe semáforo/cola acotada para inferencia, clasificación o llamadas al proveedor.

El timeout global mejora la respuesta al cliente, pero `asyncio.wait_for` no garantiza detener trabajo síncrono que ya está ejecutándose en el thread pool (`backend/app/errors.py:40-55`). Por eso el timeout no sustituye backpressure ni control de concurrencia.

**Recomendación:** aprobar primero el modelo de acceso de #12 y después implementar #13 con identidad verificable, rate limiting compartido, cuota global, límites por identidad, semáforos/cola acotada, `429` y `Retry-After`. Mantener separados los endpoints ligeros para que la saturación no afecte health checks o lecturas simples.

### R-02 — RPC de búsqueda accesibles por `anon` y con límites eludibles

**Severidad:** alta · **Issue:** #14 · **Hallazgo original:** A-03

**Estado:** pendiente.

`search_patentes_hybrid` y `patentes_similares` conceden `EXECUTE` a `anon` (`backend/migrations/002_hybrid_search_function.sql:115-116`, `:153-154`). Sus parámetros `candidate_pool`, `top_k` y `rrf_k` no se acotan dentro de PostgreSQL (`:28-33`, `:73`, `:85`, `:95-111`). Un cliente puede saltarse la validación de FastAPI y provocar consultas mucho más costosas o errores deliberados.

La RPC léxica nueva sí acota query, página y tamaño, y fija un `search_path` seguro (`backend/migrations/004_parameterized_lexical_search.sql:13-43`), pero también concede ejecución directa a `anon` (`:57-58`). Su política de acceso debe revisarse junto con las demás RPC después de decidir #12.

**Recomendación:** versionar revocaciones y grants mínimos; aplicar límites SQL independientes de FastAPI; cualificar objetos y fijar `search_path`; añadir `statement_timeout`; probar roles autorizados y no autorizados en una base efímera. Incluir las tres RPC en el inventario de #14.

### R-03 — Información potencialmente confidencial enviada a Gemini sin política visible

**Severidad:** alta · **Issue:** #17 · **Hallazgo original:** A-06

**Estado:** pendiente.

El chat envía a Gemini el mensaje, historial y contexto rehidratado de patentes (`backend/app/routes/chat.py:145-172`). La clasificación envía la descripción técnica introducida por el usuario (`backend/app/services/classification_service.py`). El frontend no presenta aviso específico, consentimiento, categorías prohibidas ni una alternativa claramente identificada que no envíe contenido al proveedor.

La redacción de logs redujo el riesgo interno: no se registran prompts, claims ni cuerpos. Sin embargo, eso no resuelve finalidad, retención, región, entrenamiento, base legal ni el posible envío de invenciones aún no publicadas.

**Recomendación:** cerrar la decisión de privacidad antes del piloto, limitar la beta a patentes públicas/datos sintéticos hasta entonces, documentar el flujo, introducir aviso y consentimiento cuando corresponda, y evaluar un modo estrictamente local para casos sensibles.

### R-04 — El repositorio no reconstruye el esquema ni su postura de permisos

**Severidad:** media-alta · **Issue:** #24 · **Hallazgo original:** M-11

**Estado:** pendiente.

La primera migración comienza con `ALTER TABLE patentes`; no existe una migración que cree la tabla base. Tampoco están versionados de forma completa owner, constraints base, RLS, políticas y grants de tabla. La propia documentación reconoce que `patentes` debe existir previamente.

Además, la migración 002 usa columnas como `apc`, `ww`, `lg_st` y `pd`, aunque la migración 003 es la que declara agregarlas. La secuencia numerada no puede garantizar una reconstrucción limpia sin depender del esquema externo preexistente.

Los scripts administrativos y el proceso web comparten el nombre `SUPABASE_KEY`. Esto no filtra secretos por sí mismo, pero facilita arrancar accidentalmente el API con una credencial privilegiada usada para cargas offline. La separación de credenciales runtime/administración debe formar parte del inventario de permisos de #24.

**Recomendación:** obtener un dump de esquema autorizado sin datos, convertirlo en baseline reproducible, ordenar dependencias, versionar RLS/grants/owners y validar reconstrucción y drift en CI. Separar nombres y entornos de credenciales administrativas y de runtime.

### R-05 — La migración 003 mantiene operaciones destructivas sin plan seguro

**Severidad:** media-alta · **Issue:** #25 · **Hallazgo original:** M-12

**Estado:** pendiente.

`backend/migrations/003_new_columns_and_unique_pn.sql` elimina duplicados conservando automáticamente el mayor `id`, borra y recrea `search_vector` e índice GIN, y no incluye prechecks, respaldo de filas, transacción explícita, estrategia de locks, ejecución online ni rollback. Que pueda repetirse sin error no implica que sea segura operativamente.

**Recomendación:** no ejecutar este archivo sin el plan de #25. Inspeccionar y exportar duplicados, aprobar una regla de merge, ensayar con volumen representativo, medir locks/tiempo, definir backup y rollback, y separar el cambio destructivo de la evolución aditiva.

## 3. Hallazgo mitigado parcialmente

### R-06 — CSP configurada, pero todavía no aplicada

**Severidad residual:** media-baja · **Hallazgo original:** M-13

**Estado:** mitigado parcialmente; #26 está cerrado.

El frontend ya versiona `Permissions-Policy`, `Referrer-Policy`, `X-Content-Type-Options`, protección de framing y HSTS en producción. La CSP, sin embargo, se sirve como `Content-Security-Policy-Report-Only` y admite `'unsafe-inline'` para scripts y estilos (`frontend/src/lib/securityHeaders.mjs:12-29`). En ese modo detecta violaciones, pero no las bloquea.

**Recomendación:** recoger reportes durante el piloto, eliminar permisos innecesarios y pasar gradualmente a `Content-Security-Policy` aplicada. No es un bloqueo para una beta controlada, pero sí una defensa pendiente antes de considerar completo el hardening del navegador.

## 4. Observaciones nuevas o residuales

### N-01 — Vulnerabilidad moderada en una dependencia transitiva frontend

`npm audit --omit=dev` detectó una vulnerabilidad moderada en `baseline-browser-mapping@2.10.8`, incorporada por Next.js y Browserslist. No se encontraron vulnerabilidades altas o críticas y npm informa que hay corrección disponible. Referencia: [GHSA-w5vr-8v7q-w6rv](https://github.com/advisories/GHSA-w5vr-8v7q-w6rv).

**Riesgo práctico:** bajo para los flujos actuales porque la librería no procesa directamente una entrada de usuario en la aplicación, pero debe actualizarse el lock y repetirse build/auditoría en el siguiente mantenimiento de dependencias. El CI actual solo falla desde severidad alta, por lo que esta alerta moderada no bloqueará un PR.

### N-02 — `/metrics` expone telemetría operativa sin control de acceso

`GET /metrics` está registrado como ruta pública (`backend/app/main.py:164-166`). No expone prompts ni credenciales, pero sí nombres de operaciones/modelos, saturación, fallbacks, cuotas locales y concurrencia. Esa información facilita reconocimiento operativo y crece en sensibilidad cuando el servicio se hace público.

**Recomendación:** restringirlo a red interna, token del collector o gateway; alternativamente, exportar métricas directamente al proveedor de observabilidad. Puede incorporarse a #13 o al trabajo de infraestructura del despliegue.

### N-03 — La validación estricta no es uniforme en todos los requests

El chat usa `extra="forbid"`, límites de listas, roles y presupuesto total (`backend/app/routes/chat.py:50-83`). En cambio, `SemanticSearchRequest` y `CpcClassificationRequest` conservan el comportamiento por defecto de ignorar campos extra; la búsqueda semántica acepta una cadena compuesta solo por espacios (`backend/app/models/patent.py:52-54`).

**Recomendación:** crear una base común de requests con `extra="forbid"`, normalizar espacios y rechazar texto vacío. Es una mejora de contrato y robustez, no una vulnerabilidad crítica porque los campos desconocidos no se ejecutan.

### N-04 — Avisos de compatibilidad en la suite Python

Las pruebas pasan, pero pytest muestra que `asyncio_default_fixture_loop_scope` no está definido y Starlette avisa que su integración actual de `TestClient` con `httpx` está deprecada a favor de `httpx2`. Conviene resolver los avisos antes de actualizar dependencias para evitar una ruptura inesperada de la suite.

## 5. Verificación de los hallazgos corregidos

| Hallazgos originales | Estado verificado | Evidencia principal |
| --- | --- | --- |
| A-01 | Corregido | Next.js actualizado a 16.3.4; auditoría npm sin vulnerabilidades altas/críticas. |
| A-04, M-02, M-15, B-04, B-05 | Corregidos en el flujo de chat | El navegador envía IDs y el servidor rehidrata contexto; límites de mensajes, historial, IDs y contexto; `sessionStorage` guarda solo versión/query/IDs. |
| A-05 | Corregido | Locks Python separados, versiones transitivas y hashes; instalación reproducible y auditoría en CI. |
| M-01 | Corregido | RPC léxica parametrizada, escape literal y límites duplicados en API/SQL. |
| M-03 | Corregido | Errores públicos estables, correlation ID y logs estructurados con allowlist de campos. |
| M-04, B-08 | Corregidos con riesgo residual cubierto por #13 | Timeouts por dependencia, reintentos acotados y cancelación frontend; el trabajo síncrono requiere backpressure. |
| M-07 | Corregido | El fallback de clasificación captura errores esperados y propaga fallos inesperados; respuesta incluye `local_fallback`. |
| M-08 | Corregido | `maybe_single`, 404 diferenciado y error recuperable en frontend para fallos de infraestructura. |
| M-09, M-10 | Corregidos | Paralelismo de lecturas independientes, respuestas resumen, una consulta de datos+conteo y políticas de revalidación. |
| M-14 | Corregido | HTTPS obligatorio, allowlist de Espacenet y validación de rutas internas del chat. |
| B-01, B-02, B-03, B-06 | Corregidos | Settings y clientes mediante `create_app`/lifespan, reutilización/cierre, liveness/readiness y CORS seguro por entorno. |
| B-07 | Corregido | OpenAPI versionado, tipos generados y validación runtime con Zod. |
| B-09 | Corregido | Paginación de tamaño constante, navegación preservada y atributos accesibles. |
| B-10 | Corregido | Métricas y logs estructurados, documentación operativa y señales de dependencias. Queda restringir `/metrics`. |
| B-11 | Corregido | Unitarias frontend, E2E con servicios falsos y CI para backend, frontend, contratos, dependencias y secretos. |
| B-12 | Corregido | Artefactos ignorados y documentación alineada con comandos, dependencias y comportamiento actual. |

## 6. Evaluación de arquitectura actual

### Fortalezas

- Separación clara entre rutas, modelos, servicios y dependencias en FastAPI.
- Factory de aplicación y lifespan que permiten pruebas sin servicios reales.
- Servicios externos encapsulados con timeouts, reintentos y métricas.
- Índice CPC validado mediante manifest, hash, forma, dtype y `allow_pickle=False`.
- Server Components para lectura y validación runtime del contrato remoto.
- Contexto del chat rehidratado desde la fuente autorizada.
- CI reproducible con tests, lint, build, E2E, OpenAPI, auditorías y Gitleaks.
- Logs sin contenido de usuario y etiquetas de métricas acotadas.

### Deuda arquitectónica que debe guiar el MVP

1. **Control plane de acceso:** #12 debe fijar una única fuente de identidad y responsabilidades entre gateway, API y base de datos.
2. **Protección de recursos:** #13 debe acotar consumo global y por usuario, no solo cuota de un modelo por proceso.
3. **Frontera de datos:** #14 y #24 deben lograr que ningún cliente directo tenga más permisos que el contrato público previsto.
4. **Privacidad por diseño:** #17 debe decidir qué contenido puede salir a Gemini antes de invitar a usuarios con casos reales.
5. **Infraestructura reproducible:** #24 y #25 deben permitir crear, migrar, recuperar y comparar entornos sin depender de conocimiento manual.

No hace falta dividir ahora el backend en microservicios. Para el MVP sigue siendo adecuada una aplicación modular única con un frontend separado, una base gestionada y, si la carga lo exige, un worker/cola para operaciones pesadas. El límite útil es aislar recursos y credenciales, no multiplicar servicios prematuramente.

## 7. Pruebas y comprobaciones ejecutadas

| Comprobación | Resultado |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m pytest` | 116 pruebas aprobadas; 2 avisos de deprecación/configuración futura. |
| `backend/.venv/Scripts/python.exe -m ruff check app exel tests` | Aprobado. |
| `backend/.venv/Scripts/python.exe scripts/export_openapi.py --check` | Aprobado; contrato sincronizado. |
| `backend/.venv/Scripts/python.exe -m pip_audit -r requirements.lock --require-hashes` | Sin vulnerabilidades conocidas. |
| `npm test` | 15 pruebas aprobadas. |
| `npm run lint` | Aprobado. |
| `npm run build` | Aprobado con Next.js 16.3.4. |
| `npm run api:check` | Aprobado. |
| `npm run test:e2e` | 6 flujos aprobados en Chromium con API falsa. |
| `npm audit --omit=dev` | 1 moderada, 0 altas, 0 críticas. |

## 8. Limitaciones de esta auditoría

- No se ejecutaron migraciones ni consultas contra Supabase.
- No se hicieron llamadas reales a Gemini ni se revisaron sus condiciones contractuales vigentes.
- No se inspeccionaron RLS, grants, owners, secretos ni configuración efectiva de entornos remotos.
- No se realizó pentesting dinámico, prueba de carga, análisis de imagen/contenedor ni auditoría de licencias.
- No se ejecutó Gitleaks localmente; sí se verificó que no hay `.env`, datasets o índices locales rastreados y el CI contiene el escaneo.
- Las garantías sobre privacidad y permisos dependen de decisiones y configuración externa aún pendientes.

## 9. Orden recomendado

1. Resolver #12: decisión de acceso e identidad.
2. En paralelo después de la decisión, implementar #13 y #14.
3. Resolver #17 antes de usar invenciones o conversaciones reales.
4. Completar #24 como baseline de datos y seguridad.
5. Ensayar y ejecutar #25 únicamente con el baseline, backup y rollback definidos.
6. Atender N-01, restringir `/metrics` y pasar CSP a modo aplicado durante el hardening del piloto.

El código ya no presenta la concentración inicial de deuda técnica. El siguiente salto de madurez depende principalmente de controles operativos y de seguridad alrededor del código: identidad, cuotas, permisos de base de datos, privacidad y recuperación del entorno.
