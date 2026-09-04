# Auditoría técnica, de arquitectura y seguridad

**Proyecto:** Patentólogos  
**Fecha:** 2026-09-02  
**Tipo de revisión:** análisis estático del repositorio y auditoría de dependencias del frontend  
**Alcance:** `backend/app`, `backend/exel`, `backend/migrations`, `backend/tests`, `frontend/src`, manifiestos, archivos de configuración y documentación.

## 1. Resumen ejecutivo

El proyecto tiene una base clara y razonablemente modular: separa rutas, modelos y servicios en FastAPI; usa modelos Pydantic; limita varios parámetros; no contiene secretos versionados detectables; evita renderizar HTML crudo; y cuenta con pruebas unitarias e integrales del backend. La validación del índice CPC, el uso de `allow_pickle=False` y la comprobación de que Gemini solo seleccione códigos recuperados son decisiones especialmente acertadas.

Sin embargo, **no se recomienda exponer la aplicación a Internet en su estado actual**. Los principales riesgos son:

1. La versión fijada de Next.js (`16.1.7`) tiene vulnerabilidades conocidas de severidad alta, incluyendo variantes de denegación de servicio, SSRF y bypass de middleware/proxy.
2. Los endpoints que consumen CPU, memoria, base de datos y cuota de Gemini son públicos y no tienen autenticación, rate limiting, cuotas, límites de concurrencia ni protección frente a abuso.
3. Las funciones RPC de Supabase están concedidas directamente al rol `anon`, y sus parámetros costosos no se acotan dentro de PostgreSQL. Un cliente puede omitir el backend y solicitar pools arbitrariamente grandes.
4. El chat acepta historial y supuestos datos de patentes enviados por el navegador sin revalidarlos contra la base de datos. Esto permite falsificar contexto, amplificar prompts y consumir cuota.
5. Las dependencias Python de producción no están fijadas ni existe un lockfile reproducible. Una instalación futura puede cambiar o romperse sin que cambie el repositorio.
6. El producto envía descripciones de invenciones, conversaciones y contenido de patentes a Gemini sin una capa visible de consentimiento, clasificación de datos o política de retención. Esto puede ser crítico si el usuario introduce material confidencial o aún no publicado.

### Distribución de hallazgos

| Severidad | Cantidad |
|---|---:|
| Crítica | 0 |
| Alta | 6 |
| Media | 15 |
| Baja | 12 |
| Total | 33 |

> La severidad expresa el riesgo potencial bajo un despliegue público. Algunos hallazgos pueden reducirse si la aplicación solo se ejecuta en una red local confiable, si Supabase tiene políticas RLS no incluidas en este repositorio o si existen controles externos en el proxy/plataforma.

## 2. Metodología y limitaciones

Se revisaron manualmente los flujos de entrada, acceso a Supabase, generación con Gemini, embeddings, carga del índice CPC, renderizado y navegación. También se inspeccionó el historial inmediato de Git, archivos rastreados, patrones de secretos y cobertura temática de las pruebas.

Se ejecutó `npm audit --omit=dev --json` contra `frontend/package-lock.json`. El resultado fue **4 paquetes de producción vulnerables, todos reportados con severidad alta**: `next`, `nanoid`, `postcss` y `sharp`. No se aplicó ningún arreglo automático.

No se ejecutaron la aplicación, migraciones, scripts de datos, llamadas a Supabase/Gemini, pruebas, linters ni builds. Tampoco se realizó pentesting dinámico. Las políticas RLS, grants preexistentes, configuración real de hosting, WAF, secretos y observabilidad externa no están presentes en el repositorio y deben auditarse por separado.

## 3. Hallazgos de severidad alta

### A-01 — Next.js 16.1.7 contiene vulnerabilidades conocidas

**Evidencia:** `frontend/package.json:13`, `frontend/package-lock.json` (`next@16.1.7`).  
**Impacto:** según el resultado local de npm, esta versión cae dentro de rangos afectados por múltiples avisos, incluidos DoS de React Server Components, bypass de middleware/proxy, SSRF y problemas de caché. No todos son necesariamente explotables con la configuración actual, pero los DoS sobre App Router/RSC sí son relevantes para este proyecto. `postcss@8.5.8`, `sharp@0.34.5` y `nanoid@3.3.11` también aparecen afectados de forma transitiva.  
**Recomendación:** actualizar Next.js a una versión estable corregida compatible —el audit propone `16.3.4` al momento de esta revisión—, regenerar el lockfile de forma controlada y validar con build, lint, pruebas y smoke tests. Revisar cada advisory para confirmar aplicabilidad antes del despliegue:

- [GHSA-q4gf-8mx6-v5v3](https://github.com/advisories/GHSA-q4gf-8mx6-v5v3)
- [GHSA-8h8q-6873-q5fj](https://github.com/advisories/GHSA-8h8q-6873-q5fj)
- [GHSA-c4j6-fc7j-m34r](https://github.com/advisories/GHSA-c4j6-fc7j-m34r)
- [GHSA-f88m-g3jw-g9cj](https://github.com/advisories/GHSA-f88m-g3jw-g9cj)
- [GHSA-r28c-9q8g-f849](https://github.com/advisories/GHSA-r28c-9q8g-f849)

### A-02 — Endpoints costosos públicos y sin controles antiabuso

**Evidencia:** no hay dependencias de autenticación en `backend/app/routes/chat.py:99-100`, `classification.py:10-16` ni `patents.py:31-43`; tampoco hay middleware de rate limiting en `backend/app/main.py:17-31`.  
**Impacto:** cualquier origen o cliente HTTP puede invocar directamente Gemini, el modelo de embeddings, el escaneo matricial de aproximadamente 400 MB y consultas vectoriales. CORS no impide llamadas desde scripts, servidores o clientes no navegador. Esto permite agotar cuota, CPU, RAM, workers, conexiones y presupuesto. El rate limiter de `GeminiFallbackClient` protege parcialmente la cuota por proceso, pero no limita usuarios, tamaño total, concurrencia ni múltiples réplicas.  
**Recomendación:** definir el modelo de acceso (privado, cuentas o API keys), autenticar operaciones costosas, implementar límites por identidad/IP y globales, cuotas diarias, límites de concurrencia, backpressure y respuestas `429` con `Retry-After`. Complementar con límites en gateway/WAF; no depender exclusivamente de controles en memoria.

### A-03 — RPCs costosos expuestos directamente al rol anónimo

**Evidencia:** `backend/migrations/002_hybrid_search_function.sql:114-116` y `153-154` conceden `EXECUTE` a `anon`. `search_patentes_hybrid` acepta `top_k`, `candidate_pool` y `rrf_k` sin validación interna (`:28-33`) y los usa en `LIMIT` y en el cálculo (`:62-111`).  
**Impacto:** quien obtenga la anon key pública del proyecto puede saltarse los límites Pydantic del backend y llamar el RPC directamente con un `candidate_pool` o `top_k` enorme, generando consumo elevado de CPU/I/O y respuestas voluminosas. También puede suministrar vectores arbitrarios. Las garantías dependen de grants/RLS externos no documentados.  
**Recomendación:** revocar `EXECUTE` a `anon` si el acceso debe pasar por el backend. Si el RPC debe ser público, fijar límites dentro de SQL mediante `LEAST/GREATEST`, rechazar dimensiones/valores inválidos, aplicar `statement_timeout`, cuotas y controles de gateway. Auditar explícitamente `GRANT` de tabla, RLS y políticas; versionarlos como migraciones.

### A-04 — El chat confía en contexto e historial controlados por el cliente

**Evidencia:** `ChatRequest` acepta `history: list[Message]` y `patents_context: list[dict]` (`backend/app/routes/chat.py:40-48`). El servidor incorpora ese contenido directamente al prompt de sistema (`:55-96`, `:101-116`). El navegador lo recupera de `sessionStorage` y lo reenvía (`frontend/src/components/FloatingChat.tsx:78-84`, `:108-115`).  
**Impacto:** un atacante puede falsificar títulos, claims, IDs y números de patente; insertar instrucciones dentro del supuesto corpus; inventar turnos del modelo; o enviar estructuras y textos muy grandes. La respuesta puede presentar datos falsos como si provinieran del catálogo y generar enlaces internos engañosos. Además, aumenta el costo por tokens y riesgo de denegación de servicio.  
**Recomendación:** aceptar únicamente IDs y mensajes del usuario; rehidratar las patentes en el servidor desde una fuente autorizada; usar roles con `Literal`; limitar cantidad y longitud acumulada del historial; truncar por tokens; separar claramente instrucciones y datos no confiables; y advertir que el contenido recuperado puede contener prompt injection. Para conversaciones persistentes, almacenar el historial del lado servidor y asociarlo a una identidad/sesión.

### A-05 — Cadena de suministro Python no reproducible

**Evidencia:** todas las dependencias de producción en `backend/requirements.txt` carecen de versión o hash. `requirements-dev.txt` solo fija herramientas de prueba y hereda ese archivo. No existe `pyproject.toml`, lockfile Python ni política automatizada de actualizaciones.  
**Impacto:** dos despliegues desde el mismo commit pueden instalar versiones distintas; una versión mayor incompatible o comprometida puede entrar sin revisión; y no es posible asociar con precisión el artefacto desplegado a sus CVE. Dependencias pesadas como PyTorch/Transformers llegan transitivamente sin control directo.  
**Recomendación:** declarar rangos directos deliberados y generar un lock con hashes por plataforma (por ejemplo, `uv.lock` o `pip-tools`). Separar runtime, ML, scripts offline y desarrollo. Incorporar `pip-audit`/OSV y actualización automatizada en CI, manteniendo pruebas de compatibilidad.

### A-06 — Riesgo de confidencialidad al enviar invenciones a un tercero

**Evidencia:** la descripción ingresada en el clasificador se incluye completa en el prompt de Gemini (`backend/app/services/classification_service.py:223-247`). El chat envía mensaje, historial, abstracts, descripción y claims (`backend/app/routes/chat.py:55-119`). La UI solo muestra una advertencia general de revisión técnica, no una advertencia de tratamiento de datos antes del envío.  
**Impacto:** un usuario puede pegar una invención aún no presentada, secretos empresariales o información personal. El contenido sale hacia un proveedor externo, con posibles consecuencias contractuales, de privacidad y de novedad/divulgación según jurisdicción y condiciones de servicio.  
**Recomendación:** realizar una evaluación legal y de privacidad; documentar proveedor, finalidad, región, retención y entrenamiento; obtener consentimiento informado antes del envío; prohibir o detectar datos sensibles; minimizar/redactar contenido; ofrecer un modo local sin Gemini; y registrar la base legal y el flujo de datos. No guardar prompts completos en logs.

## 4. Hallazgos de severidad media

### M-01 — Posible inyección o alteración de filtros PostgREST

**Evidencia:** `backend/app/services/patent_service.py:50-59` interpola directamente la consulta del usuario en la sintaxis cruda de `.or_()`. Solo reemplaza comas. `q` no tiene longitud máxima (`backend/app/routes/patents.py:20`).  
**Impacto:** caracteres significativos de PostgREST —paréntesis, puntos, comodines y operadores— pueden provocar filtros inesperados, errores o consultas costosas. Esto no equivale necesariamente a SQL injection, pero sí rompe la frontera de datos/código del filtro.  
**Recomendación:** evitar construir expresiones PostgREST con strings del usuario. Usar un RPC parametrizado, búsqueda FTS o una función de escape completa y probada. Añadir longitud máxima y casos adversariales.

### M-02 — Sin límites de tamaño efectivos para chat

**Evidencia:** `message`, `Message.content`, cantidad de `history` y cantidad/tamaño de `patents_context` no tienen `Field(max_length=...)` ni límites de lista (`backend/app/routes/chat.py:40-48`). El corte a 20 patentes ocurre después de deserializar todo (`:61`).  
**Impacto:** cuerpos muy grandes consumen ancho de banda, memoria, validación y tokens. El historial crece en cada turno y se retransmite completo.  
**Recomendación:** limitar body en proxy/ASGI; usar modelos Pydantic estrictos; acotar mensaje, turnos, IDs y presupuesto total de tokens; resumir o recortar historial.

### M-03 — Errores internos se devuelven al cliente

**Evidencia:** `backend/app/routes/chat.py:126-128` devuelve `detail=str(e)` para excepciones inesperadas. El frontend muestra ese detalle (`FloatingChat.tsx:117-129`). La ruta de clasificación también expone rutas locales y detalles del índice mediante `str(exc)` (`classification.py:17-18`; `classification_service.py:155-169`).  
**Impacto:** puede revelar rutas, nombres internos, mensajes del SDK o detalles operativos útiles para reconocimiento.  
**Recomendación:** responder con códigos y mensajes públicos estables; registrar internamente la excepción con stack trace y correlation ID; filtrar secretos y datos del usuario.

### M-04 — Sin timeouts, cancelación ni política robusta de resiliencia

**Evidencia:** las llamadas a Gemini (`gemini_client.py:141-146`), Supabase (`patent_service.py`) y `fetch` del frontend (`frontend/src/lib/api.ts:101-180`) no configuran timeouts ni cancelación.  
**Impacto:** peticiones colgadas ocupan workers/conexiones; navegación o cierre del componente no cancela trabajo; una caída parcial se propaga al usuario.  
**Recomendación:** timeouts por dependencia, `AbortController` en cliente, cancelación al desconectar si es viable, reintentos solo en operaciones idempotentes con backoff/jitter, circuit breaker y presupuestos de tiempo end-to-end.

### M-05 — Rate limiter de Gemini es local y reserva fallos como consumo

**Evidencia:** contadores en memoria por instancia (`backend/app/services/gemini_client.py:50-109`), cuotas codificadas (`:39-43`) y reserva antes de la llamada (`:136-146`).  
**Impacto:** múltiples workers o réplicas no comparten estado; reinicios restablecen contadores; cambios de cuota requieren despliegue; y fallos no contabilizados por el proveedor consumen capacidad local hasta expirar. La ventana de 24 h tampoco coincide con el reset real reconocido en el propio comentario.  
**Recomendación:** tratar los límites locales como optimización, no como seguridad. Centralizar cuotas en Redis/gateway o consultar metadatos del proveedor; configurar modelos y límites por entorno; clasificar errores transitorios; exponer métricas sin publicar claves.

### M-06 — Trabajo intensivo sin aislamiento ni control de concurrencia

**Evidencia:** cada clasificación calcula un embedding y multiplica contra todo el índice (`classification_service.py:96-123`); el índice memmap y modelo son singletons de proceso (`dependencies.py:8-23`, `embedding_service.py:17-28`). Las rutas síncronas ejecutan esa labor durante la petición.  
**Impacto:** varias peticiones simultáneas pueden saturar CPU, threads de PyTorch, memoria y ancho de banda de disco, degradando también endpoints ligeros. Cada worker carga su propia copia/modelo.  
**Recomendación:** separar workloads ML del API web o usar una cola; limitar concurrencia con semáforo; dimensionar workers y threads explícitamente; cachear consultas normalizadas; precalentar con readiness independiente; medir P95/P99 y memoria por réplica.

### M-07 — Cascada silenciosa convierte errores de programación en resultados degradados

**Evidencia:** `ClassificationService.recommend` captura cualquier `Exception` y devuelve fallback (`classification_service.py:89-94`).  
**Impacto:** errores de esquema, bugs o problemas de programación quedan ocultos como una respuesta aparentemente válida, dificultando detección y pudiendo mostrar clasificaciones de menor calidad sin distinguir la causa.  
**Recomendación:** capturar únicamente errores esperados del proveedor/parsing; propagar o alertar sobre fallos inesperados; devolver un indicador estructurado del modo `local_fallback`; instrumentar frecuencia y causa.

### M-08 — Acceso a detalle puede convertir “no encontrado” en 500

**Evidencia:** `PatentService.get_by_id` usa `.single().execute()` (`patent_service.py:33-41`) y la ruta solo comprueba un retorno falsy (`routes/patents.py:66-74`). PostgREST normalmente responde con error cuando `.single()` encuentra cero filas.  
**Impacto:** IDs inexistentes pueden escapar como excepción de infraestructura en vez de 404. El frontend además transforma cualquier fallo en `notFound()` (`frontend/src/app/patentes/[id]/page.tsx:29-34`), ocultando caídas reales como inexistencia.  
**Recomendación:** usar `maybe_single()` o traducir explícitamente el código “0 rows” a 404; mapear timeouts/5xx a una página de error/reintento, no a 404; probar con el cliente Supabase real o un contrato fiel.

### M-09 — Waterfalls de red evitables en Server Components

**Evidencia:** una búsqueda espera primero `searchSemantic` y después `fetchPatents` (`frontend/src/app/page.tsx:29-40`). El detalle espera la patente antes de solicitar similares (`frontend/src/app/patentes/[id]/page.tsx:29-44`), aunque el comentario afirma que es paralelo.  
**Impacto:** se suma latencia de red innecesaria y empeora TTFB.  
**Recomendación:** iniciar peticiones independientes juntas con `Promise.all`/`Promise.allSettled`; considerar un endpoint agregado; usar límites de `Suspense` para streaming; evitar calcular el total del corpus en cada búsqueda si puede cachearse.

### M-10 — Todo el fetching desactiva caché y repite conteos costosos

**Evidencia:** todas las funciones de `frontend/src/lib/api.ts:101-180` usan `cache: "no-store"`. `get_all` y `search` realizan un count y una consulta de datos separadas (`patent_service.py:17-31`, `:43-78`).  
**Impacto:** navegación repetida golpea Supabase en cada render; `count="exact"` puede ser costoso en tablas grandes; no hay deduplicación o revalidación para datos relativamente estables.  
**Recomendación:** definir frescura por caso, usar caché/revalidación de Next para listados/detalles públicos, cachear el total, considerar conteos estimados y medir el plan SQL. Mantener `no-store` solo donde la frescura lo exige.

### M-11 — Migraciones incompletas como fuente única del esquema y permisos

**Evidencia:** el README reconoce que no se crea la tabla base. No hay migraciones para RLS, políticas, grants completos, constraints de dominio ni rollback. `pd` es texto (`003_new_columns_and_unique_pn.sql:30-33`) y casi todos los campos admiten null.  
**Impacto:** no se puede reconstruir ni auditar un entorno desde cero; dev/staging/prod pueden divergir; fechas inválidas impiden rangos fiables; la postura de seguridad queda fuera de control de versiones.  
**Recomendación:** versionar esquema completo, propietarios, RLS, grants, constraints, funciones y datos de referencia; usar `date`/`timestamptz` según corresponda; añadir checks; introducir una herramienta de migraciones con tabla de versiones y validación en CI.

### M-12 — Migración 003 borra datos y reconstruye un índice sin salvaguardas

**Evidencia:** elimina duplicados conservando la fila de mayor ID (`003_new_columns_and_unique_pn.sql:63-71`) y elimina/recrea `search_vector` e índice (`:87-106`). No hay transacción explícita, respaldo, auditoría de duplicados ni estrategia online.  
**Impacto:** puede perderse información válida de filas duplicadas y producir bloqueo/downtime o un estado parcial si falla una sentencia. La fila más reciente no necesariamente es la más completa.  
**Recomendación:** ejecutar prechecks y exportar duplicados; definir reglas de merge; envolver cambios compatibles en transacción; usar estrategia online para índices/columnas según volumen; ensayar y medir locks en staging; documentar rollback.

### M-13 — Falta de headers de seguridad y política CSP

**Evidencia:** `frontend/next.config.ts` está vacío y no hay middleware/gateway versionado para CSP, HSTS, `Referrer-Policy`, `Permissions-Policy` o protección de framing.  
**Impacto:** se pierde defensa en profundidad frente a XSS, clickjacking, fuga de referrer y uso innecesario de APIs del navegador.  
**Recomendación:** definir headers en Next o, preferiblemente, en el edge/proxy con una CSP probada. Comenzar con `Content-Security-Policy-Report-Only`; restringir `connect-src` al backend/Gemini indirecto y verificar compatibilidad con Next/fonts.

### M-14 — Enlaces externos provenientes de datos no se validan

**Evidencia:** `patent.espacenet` se usa directamente como `href` (`frontend/src/app/patentes/[id]/page.tsx:154-164`). Los enlaces externos de Markdown generado por Gemini también se hacen clicables (`FloatingChat.tsx:193-204`).  
**Impacto:** datos comprometidos o una salida manipulada del modelo pueden generar enlaces de phishing o esquemas no deseados. React/React Markdown aportan algunas protecciones, pero no sustituyen una política de URL explícita.  
**Recomendación:** parsear con `URL`, permitir solo `https:` y, para Espacenet, una allowlist de dominios. Para el chat, deshabilitar enlaces externos o mostrar confirmación/dominio visible.

### M-15 — Datos de búsqueda completos se duplican en `sessionStorage`

**Evidencia:** `SearchContextStore` serializa todos los resultados (`frontend/src/components/SearchContextStore.tsx:10-14`), y `FloatingChat` los parsea sin validación (`:78-84`).  
**Impacto:** se duplican datos y abstracts en memoria/almacenamiento accesible a cualquier script del mismo origen; una entrada corrupta produce una excepción; el estado puede quedar obsoleto o manipulado.  
**Recomendación:** guardar solo IDs y query con un esquema versionado; validar/encapsular `JSON.parse`; aplicar TTL; rehidratar en servidor; limpiar al cerrar sesión si se incorpora autenticación.

## 5. Hallazgos de severidad baja

### B-01 — Configuración global en tiempo de importación

`settings = Settings()` (`backend/app/config.py:15`) exige Supabase y Gemini incluso para iniciar health checks o funciones que no los usan. Los clientes globales (`routes/chat.py:14`) complican pruebas, rotación de claves y lifecycle. Usar `SettingsConfigDict`, caché de dependencia, factories e inicialización/lifespan explícito. Validar entorno de producción y permitir que funcionalidades opcionales fallen de forma aislada.

### B-02 — Health check superficial

`backend/app/main.py:34-36` siempre devuelve OK sin distinguir liveness de readiness. Añadir `/health/live` y `/health/ready`; comprobar de forma acotada configuración, artefactos y dependencias necesarias, sin filtrar secretos ni provocar cargas pesadas.

### B-03 — CORS de desarrollo habilitado por defecto

`allow_local_network_origins=True` (`config.py:8`) y la regex admite cualquier origen HTTP en rangos privados (`main.py:9-27`). Aunque CORS no es control de autenticación, el default es arriesgado para producción. Usar default seguro (`False`), lista explícita por entorno y métodos/headers mínimos.

### B-04 — Contratos Pydantic demasiado permisivos

`Message.role` es `str`, el contexto usa `dict`, y varios modelos de salida ignoran campos extra (`models/patent.py:4-12`). Definir `Literal["user", "model"]`, modelos específicos, `extra="forbid"` para entradas y constraints de lista/texto. En chat, cualquier rol distinto de `user` se convierte silenciosamente en `model` (`routes/chat.py:107-110`).

### B-05 — Defaults mutables poco expresivos

`history = []` y `patents_context = []` (`routes/chat.py:47-48`) son manejados de forma segura por Pydantic v2, pero el patrón es fácil de copiar a Python normal y confunde intención. Usar `Field(default_factory=list)`.

### B-06 — El API síncrono crea un cliente Supabase por petición

`get_supabase()` llama `create_client` cada vez (`dependencies.py:11-16`). Verificar si el SDK reutiliza conexiones; preferir lifecycle y pool explícitos, o un cliente singleton seguro para concurrencia. Evaluar SDK async si se adopta FastAPI async.

### B-07 — Tipos frontend duplicados y sin validación runtime

`frontend/src/lib/api.ts` replica manualmente los modelos y devuelve `res.json()` con cast implícito. Ya existe una discrepancia: `Patent.id/pn` son opcionales en backend pero obligatorios en frontend. Generar cliente/tipos desde OpenAPI y validar respuestas críticas con un esquema runtime.

### B-08 — Manejo de errores del chat cliente incompleto

La carga de patente en `FloatingChat.tsx:69-77` no comprueba `r.ok`, no tiene `.catch()` y puede aceptar un body de error como patente. `JSON.parse` tampoco se protege. Añadir control de estado, error visible, cancelación y validación de payload.

### B-09 — Paginación O(totalPages) y accesibilidad incompleta

`Pagination.tsx:23-34` itera por todas las páginas aunque solo renderiza una ventana. Con corpus grande esto escala innecesariamente. Calcular directamente los pocos números visibles. Añadir `aria-label`, `aria-current="page"` y labels a botones solo-icono (limpiar/cerrar/enviar).

### B-10 — Falta una estrategia formal de observabilidad

Solo hay logs puntuales en chat/clasificación. No hay configuración estructurada, request/correlation ID, métricas, tracing, niveles por entorno ni redacción. Añadir latencia por endpoint/dependencia, errores, fallbacks, rate limits, uso de tokens/cuota, saturación y health de índice, evitando contenido sensible.

### B-11 — No hay pruebas frontend, E2E ni pipeline CI

El backend tiene una suite valiosa, pero no existe configuración de pruebas del frontend ni workflows CI. Tampoco se exige cobertura. Añadir unit/component tests, E2E de búsqueda/chat/clasificación, pruebas de accesibilidad, contrato OpenAPI y CI con lint, typecheck, build, tests, auditoría de dependencias y secret scanning.

### B-12 — Higiene y documentación técnica mejorables

`backend/package-lock.json` está vacío y no corresponde a un paquete Node; debe eliminarse si no tiene propósito. El directorio `backend/exel` contiene un typo que afecta claridad. `ruff` está en dependencias de producción. Algunos comentarios son inexactos: PostgreSQL `ts_rank_cd` no es BM25 estricto y el detalle afirma cargar similares “en paralelo” aunque es secuencial. Mantener documentación alineada con el comportamiento real.

## 6. Revisión de arquitectura

### Aspectos positivos

- Separación inicial de rutas, servicios y modelos.
- Inyección de `PatentService` y `ClassificationService`, lo que facilita dobles de prueba.
- Índice CPC autocontenido, validado por versión, hash, shape y dtype.
- Recuperación antes de generación y validación de códigos contra candidatos, reduciendo alucinaciones.
- Modelos de respuesta explícitos que evitan exponer accidentalmente el embedding en endpoints normales.
- Límites razonables en `top_k` del API y longitud del clasificador.
- Frontend usa Server Components para páginas de lectura y evita `dangerouslySetInnerHTML`.
- Tests backend cubren happy paths, fallbacks, concurrencia del limiter, CORS y errores principales.

### Dirección recomendada

La estructura actual es adecuada para un prototipo, pero antes de escalar conviene establecer cuatro fronteras claras:

1. **API pública:** autenticación/autorización, cuotas, validación, contratos, errores estables y observabilidad.
2. **Aplicación:** casos de uso de búsqueda, detalle, chat y clasificación sin acoplarlos al SDK de Supabase o Gemini.
3. **Infraestructura:** adaptadores de Supabase, Gemini, embeddings e índice CPC, todos con timeout, métricas y errores tipados.
4. **Procesamiento offline:** scripts de importación/indexación separados del runtime web, con configuración y dependencias propias.

No es necesario imponer una arquitectura compleja. Protocolos pequeños (`PatentRepository`, `TextGenerator`, `Embedder`), excepciones de dominio y factories centralizadas serían suficientes para mejorar pruebas, portabilidad y resiliencia.

## 7. Calidad y pruebas: brechas prioritarias

Agregar pruebas para:

- autenticación, autorización, rate limits y límites de body/historial;
- filtros PostgREST con comas, puntos, paréntesis, `%`, Unicode y entradas largas;
- 404 real de Supabase, timeout, 429, 5xx y respuestas malformadas;
- prompt injection en descripción, claims, abstracts e historial;
- concurrencia real del modelo/índice y consumo máximo de memoria;
- RLS/grants/RPC desde roles `anon`, `authenticated` y backend;
- compatibilidad de migraciones desde una base vacía y desde cada versión previa;
- contrato generado entre FastAPI y TypeScript;
- URL schemes y dominios externos;
- navegación rápida/cancelación, sessionStorage corrupto y estados de error;
- accesibilidad con teclado, focus, lectores de pantalla y viewport móvil;
- regresión de ranking con un dataset de evaluación versionado y métricas como Recall@K/nDCG.

## 8. Operación, despliegue y cadena de suministro

- Crear imágenes reproducibles con usuario no root, filesystem de solo lectura cuando sea posible, health checks y SBOM.
- Separar el artefacto CPC del contenedor y verificar su hash antes de promoverlo.
- Fijar versiones de Python/Node y dependencias; usar `npm ci` y lock Python con hashes.
- Ejecutar SAST, secret scanning, dependency review, auditoría de contenedores y licencias en CI.
- Proteger ramas, exigir revisión y pruebas, y documentar rollback.
- Gestionar secretos en el proveedor, con rotación y mínimo privilegio. Confirmar que `SUPABASE_KEY` del API sea `anon` salvo tareas administrativas separadas.
- Separar credenciales de lectura del backend y credenciales administrativas de scripts. Nunca reutilizar `service_role` en el proceso web.
- Mantener backups y probar restauración antes de migraciones destructivas.
- Añadir entornos de staging y pruebas de carga para búsqueda vectorial y clasificación.

## 9. Plan de remediación recomendado

### Antes de cualquier despliegue público

1. Actualizar Next.js/dependencias y repetir la auditoría.
2. Revocar o limitar los RPC anónimos; versionar RLS/grants.
3. Proteger chat, búsqueda semántica y clasificador con autenticación, cuotas y límites de concurrencia/body.
4. Hacer que el servidor reconstruya el contexto del chat desde IDs confiables.
5. Definir y comunicar el tratamiento de información confidencial enviada a Gemini.
6. Dejar de exponer excepciones internas.

### Corto plazo

1. Fijar dependencias Python y añadir auditorías automáticas.
2. Incorporar timeouts, cancelación, errores tipados y observabilidad.
3. Corregir filtros PostgREST y el 404 de `.single()`.
4. Paralelizar fetches independientes y definir una estrategia de caché.
5. Añadir headers de seguridad y validación de URLs.
6. Completar esquema/migraciones y estrategia de rollback.

### Mediano plazo

1. Aislar trabajo ML y controlar concurrencia/capacidad.
2. Generar el cliente frontend desde OpenAPI.
3. Añadir pruebas frontend/E2E, de seguridad, carga y migraciones en CI.
4. Separar dependencias y credenciales de runtime versus procesos offline.
5. Establecer SLO, métricas de calidad del ranking y alertas de costo/cuota.

## 10. Conclusión

El código muestra buenas decisiones para un prototipo funcional y tiene mejor cobertura backend que muchos proyectos en esta etapa. El riesgo principal no es una única vulnerabilidad artesanal, sino la combinación de **servicios costosos sin control de acceso**, **RPCs anónimos sin límites internos**, **dependencias vulnerables/no reproducibles** y **datos potencialmente confidenciales enviados a un LLM externo**. Resolver los seis hallazgos altos debería ser condición de salida para un despliegue público; después, las mejoras medias elevarán de forma notable la disponibilidad, mantenibilidad y capacidad de evolución.
