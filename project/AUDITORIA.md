# Auditoría técnica — NextInventia (Patentólogos)

**Fecha:** 2026-08-21
**Rama auditada:** `develop` @ `2cef30e` (incluye todo lo mergeado a `main` más el PR #9 `ft/description-RAG`)
**Alcance:** `backend/` (FastAPI + Supabase + Gemini) y `frontend/` (Next.js 16)
**Metodología:** lectura completa de código fuente, `git grep` para confirmar (no suponer) referencias antes de reportar código muerto, `ruff` y `eslint` para higiene de imports/variables, `pip-audit` y `npm audit` para dependencias, y **verificación en vivo** contra un backend real (con credenciales reales de Supabase/Gemini, en llamadas de solo lectura) para confirmar dos hallazgos que de otro modo habrían quedado como "sospecha" en vez de "confirmado".

No se modificó código. Todo lo que sigue es diagnóstico.

---

## 1. Funcionalidad y correctitud

### 1.1 — [ALTO] `GET /patentes/{id}` devuelve 500 en vez de 404 para un id inexistente (CONFIRMADO EN VIVO)

- **Ubicación:** [`backend/app/services/patent_service.py:33-41`](backend/app/services/patent_service.py#L33-L41), [`backend/app/routes/patents.py:66-74`](backend/app/routes/patents.py#L66-L74)
- **Descripción:** `PatentService.get_by_id()` usa `.select(...).eq("id", patent_id).single().execute()`. El método `.single()` del cliente `postgrest-py` **lanza una excepción** (`postgrest.exceptions.APIError`, código `PGRST116`, "Cannot coerce the result to a single JSON object") cuando la consulta devuelve 0 filas, en vez de devolver un objeto con `data=None`. El código de la ruta asume lo segundo (`if not patent: raise HTTPException(404)`), pero esa rama nunca se alcanza: la excepción se propaga sin capturar y termina como un 500 genérico.

  **Verificación en vivo:** levanté el backend localmente contra la base de datos real y pedí `GET /patentes/999999999`. Resultado: `HTTP 500`, con este traceback en el servidor:
  ```
  postgrest.exceptions.APIError: {'message': 'Cannot coerce the result to a single JSON object', 'code': 'PGRST116', 'hint': None, 'details': 'The result contains 0 rows'}
  ```
- **Por qué los tests no lo detectaron:** existe un test (`tests/integration/test_patent_routes.py:177-188`, `test_get_patente_inexistente_retorna_404`) que *parece* cubrir este caso, pero mockea `.execute()` para devolver directamente `MagicMock(data=None)` — un comportamiento que **no refleja al cliente real**. El test pasa, pero prueba un camino que no ocurre en producción. Es un ejemplo concreto de "cobertura que da falsa confianza" (justo lo que pediste evaluar).
- **Recomendación:** envolver la llamada en `try/except postgrest.exceptions.APIError` dentro de `get_by_id()` y devolver `None` cuando el código sea `PGRST116` (o cambiar el mock del test para que reproduzca el error real, lo cual habría hecho fallar el test y expuesto el bug antes).

### 1.2 — [MEDIO] Dos de cinco endpoints de patentes no tienen ningún test

- **Ubicación:** `backend/app/routes/patents.py` — `POST /patentes/search/semantic` y `GET /patentes/{id}/similares`
- **Descripción:** confirmé con `grep -rn "search/semantic\|similares" tests/` que no hay **ninguna** ocurrencia en `tests/integration/test_patent_routes.py` ni en `tests/unit/test_patent_service.py`. Estos dos endpoints llaman a funciones RPC de Supabase (`search_patentes_hybrid`, `patentes_similares`) y son parte central del producto (búsqueda híbrida y "patentes similares"), pero no hay cobertura de que el mapeo de payload, el manejo de RPC vacío, o errores de la función RPC se comporten como se espera.
- **Recomendación:** agregar tests unitarios (mockeando `client.rpc(...)`) y de integración para ambos, siguiendo el patrón ya usado en `test_patent_service.py`/`test_patent_routes.py` para `get_all`/`search`.

### 1.3 — [BAJO] `PatentService.search()` no escapa comodines de `ILIKE`

- **Ubicación:** [`backend/app/services/patent_service.py:43-59`](backend/app/services/patent_service.py#L43-L59)
- **Descripción:** el código sanitiza la coma (`query.replace(",", " ")`, necesario porque es el separador de PostgREST), pero no escapa `%` ni `_`, que son comodines de `LIKE`/`ILIKE` en Postgres. Si un usuario busca literalmente `"50%"`, el `%` se interpreta como comodín en vez de carácter literal, devolviendo resultados más amplios de lo esperado. No es un problema de seguridad (ver 2.6), es un bug de correctitud silencioso.
- **Recomendación:** escapar `%` y `_` (ej. `query.replace("%", "\\%").replace("_", "\\_")`) antes de interpolar en el patrón `ilike`.

### 1.4 — [MEDIO] Manejo de errores inconsistente entre rutas, y un leak menor de mensaje interno en `chat.py`

- **Ubicación:** [`backend/app/routes/patents.py`](backend/app/routes/patents.py) (sin manejo explícito salvo el 404 roto de 1.1), [`backend/app/routes/classification.py:15-18`](backend/app/routes/classification.py#L15-L18) (`CpcIndexError` → 503), [`backend/app/routes/chat.py:118-128`](backend/app/routes/chat.py#L118-L128) (`RuntimeError`/`ClientError` → 502, cualquier otra excepción → 500 con `detail=str(e)`)
- **Descripción:** cada router maneja errores a su manera, sin un patrón compartido ni un exception handler global de FastAPI. En particular, `chat.py` devuelve el mensaje crudo de cualquier excepción no prevista (`str(e)`) directamente en el `detail` de la respuesta 500 — no es tan grave como el caso de 2.4 (no hay rutas de archivo típicamente), pero sigue siendo información interna no pensada para el cliente.
- **Recomendación:** definir un `exception_handler` global en `main.py` para excepciones no controladas (log interno + mensaje genérico al cliente), y estandarizar los `except` específicos de cada router para que todos devuelvan `detail` con mensajes pensados para el usuario final, nunca el `str()` crudo de la excepción.

### 1.5 — Código muerto: confirmado que **no hay** código muerto adicional

- **Descripción:** el código muerto que existía (`backend/app/database.py`, `frontend/src/components/PatentChat.tsx`) ya fue eliminado en un cambio anterior (rama `chore/tech-debt-cleanup`, mergeada tanto a `main` como a `develop`). Verifiqué con `git grep` que no quedan referencias colgantes a ninguno de los dos.
- Además, confirmé referencias cruzadas para **todos** los módulos de `app/services/`, `app/routes/`, `app/models/` (backend) y **todos** los componentes de `frontend/src/components/` (frontend): cada uno se importa al menos una vez desde otro archivo. No se encontró ningún archivo ni componente huérfano.
- `ruff check .` (backend, con la configuración real del proyecto en `ruff.toml`: `E, F, W, I, N, UP`) y `eslint` (frontend) no reportan ningún import ni variable sin usar.
- **Severidad:** solo observación — se documenta como verificación positiva, no como hallazgo a resolver.

### 1.6 — [BAJO] Archivo residual: `backend/package-lock.json`

- **Ubicación:** [`backend/package-lock.json`](backend/package-lock.json)
- **Descripción:** es un lockfile de npm vacío (`{"name": "backend", "lockfileVersion": 3, "requires": true, "packages": {}}`), trackeado por git, dentro de la carpeta del backend en Python. Casi seguro producto de haber corrido `npm install` por accidente desde ese directorio. No tiene ningún propósito.
- **Recomendación:** eliminarlo (`git rm backend/package-lock.json`).

---

## 2. Seguridad

### 2.1 — [ALTO] Sin rate limiting ni autenticación en endpoints que consumen la API de Gemini (de pago)

- **Ubicación:** [`backend/app/routes/chat.py`](backend/app/routes/chat.py) (`POST /chat/`), [`backend/app/routes/classification.py`](backend/app/routes/classification.py) (`POST /clasificacion/cpc/recommend`)
- **Descripción:** confirmé con `grep` en todo `app/` que no existe ningún mecanismo de autenticación (`APIKeyHeader`, `OAuth2`, `HTTPBearer`) ni de rate limiting a nivel HTTP (`slowapi` no está en `requirements.txt`, no hay ningún `@limiter` ni middleware de límite de peticiones). El único control de tasa que existe es el interno de `GeminiFallbackClient` (protege la cuota de Gemini, no protege el endpoint de uso abusivo). Cualquiera que descubra la URL del backend puede llamar `/chat/` o `/clasificacion/cpc/recommend` tantas veces como quiera.
- **Impacto:** costo económico directo (cada llamada exitosa consume cuota de Gemini, y Gemini es un servicio de pago más allá del free tier), y denegación de servicio de facto para usuarios legítimos si alguien agota la cuota diaria/por-minuto de los 3 modelos de la cascada.
- **Recomendación:** agregar rate limiting por IP (o por API key simple) a nivel de aplicación en estos dos endpoints como mínimo — no hace falta un sistema de autenticación completo para empezar, un límite razonable (ej. N peticiones/minuto por IP) ya reduce el riesgo drásticamente.

### 2.2 — [ALTO] ~~No se pudo confirmar el estado de Row Level Security (RLS) en Supabase~~ — **RESUELTO (2026-09-06)**

- **Ubicación:** las migraciones versionadas (hoy en `supabase/migrations/`, entonces en `backend/migrations/`): ausencia de `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` o `CREATE POLICY`; `backend/.env` (comentario `#anon key` sobre la variable entonces llamada `SUPABASE_KEY`, hoy `SUPABASE_ANON_KEY`)
- **Descripción original:** revisé las 3 migraciones versionadas y ninguna habilita RLS ni define políticas para la tabla `patentes` (solo hay `GRANT EXECUTE` sobre las dos funciones RPC, a `anon, authenticated`). Esto **no confirmaba** que RLS estuviera deshabilitado en la base de datos real — pudo configurarse manualmente desde el dashboard de Supabase, fuera de control de versiones — pero si así fue, no quedaba documentado en el repositorio, lo cual era en sí mismo un problema de trazabilidad para un equipo.
- **Por qué importaba:** el backend usa la `anon key`, una clave diseñada para ser de bajo privilegio *siempre que RLS esté activo*. Si RLS estaba deshabilitado (o con políticas de escritura para `anon`), esa misma clave permitía leer/escribir la tabla directamente vía la REST API de Supabase, completamente por fuera del backend FastAPI.
- **Estado real confirmado por el equipo:** RLS **sí estaba habilitado**, pero con 3 políticas para `anon`: `SELECT`, `UPDATE` y `ALL` (`"Allow public read access"`, `"Allow public update access"`, `"Allow all access"`) — es decir, la anon key sí podía escribir/borrar libremente sobre `patentes`, confirmando el riesgo señalado.
- **Resolución aplicada:**
  1. Se separaron las claves por responsabilidad: el backend de producción sigue usando `SUPABASE_ANON_KEY` (solo lectura), y los 3 scripts de escritura en `backend/exel/` (`upload_to_supabase.py`, `generate_embeddings.py`, `cluster_patentes.py`) ahora usan `SUPABASE_SERVICE_ROLE_KEY` (bypassa RLS por diseño).
  2. Se eliminaron las 3 políticas permisivas de `anon` y se dejó una sola: `SELECT` únicamente.
  3. Se versionó el estado final en **[`supabase/migrations/20260906173200_rls_policies.sql`](supabase/migrations/20260906173200_rls_policies.sql)** (originalmente `backend/migrations/004_rls_policies.sql`; movido al adoptar el Supabase CLI, ver 2.9).
  4. Se verificó en vivo, después del cambio, que `GET /patentes/`, `GET /patentes/{id}`, `POST /patentes/search/semantic` y `GET /patentes/{id}/similares` siguen respondiendo 200 (ninguno necesita escribir).
- **Pendiente menor detectado durante la resolución (no bloqueante):** las funciones RPC (`search_patentes_hybrid`, `patentes_similares`) están `SECURITY INVOKER` (default) y tienen `GRANT EXECUTE` también para `authenticated`, pero no existe ninguna política de `SELECT` para ese rol sobre `patentes`. Hoy no tiene efecto (la app no autentica usuarios), pero si se agrega login vía Supabase Auth en el futuro, un usuario `authenticated` real obtendría 0 filas de estos RPC hasta agregar la política correspondiente. Documentado también en el propio `004_rls_policies.sql`.

### 2.3 — [ALTO] Dependencias con vulnerabilidades conocidas — frontend (Next.js)

- **Ubicación:** `frontend/package.json` (`"next": "16.1.7"`)
- **Descripción:** `npm audit --omit=dev` reporta **4 vulnerabilidades de severidad alta** en la versión instalada de Next.js, incluyendo:
  - SSRF en Server Actions sobre servidores custom (`GHSA-89xv-2m56-2m9x`)
  - SSRF en rewrites vía hostname de destino controlado por atacante (`GHSA-p9j2-gv94-2wf4`)
  - **Divulgación no autenticada de endpoints internos de Server Function** (`GHSA-955p-x3mx-jcvp`)
  - Denegación de servicio en Server Actions y en la API de optimización de imágenes vía SVG
  - Vulnerabilidades heredadas de `postcss` y `sharp` (dependencias transitivas de `next`)
  - Fix disponible: actualizar a `next@16.3.4`.
- **Nota de exploitabilidad:** no encontré uso de Server Actions (`"use server"`) en el código actual — el frontend consume el backend vía `fetch()` normal — así que el impacto directo de las advisories relacionadas a Server Actions es probablemente bajo *hoy*, pero la versión sigue siendo vulnerable y las advisories de SSRF en rewrites/middleware aplican independientemente de si se usan Server Actions.
- **Recomendación:** actualizar `next` a `16.3.4` o superior (`npm audit fix --force` lo instala, pero recomiendo hacerlo de forma controlada y correr la suite de tests/build después, no a ciegas).

### 2.4 — [MEDIO] Dependencias con vulnerabilidades conocidas — backend (Python)

- **Ubicación:** `backend/requirements.txt` / `backend/requirements-dev.txt`
- **Descripción:** `pip-audit` sobre el entorno virtual actual reporta **45 vulnerabilidades conocidas en 14 paquetes**. La mayoría son de paquetes indirectos o de tooling de desarrollo (`pip`, `setuptools`, `pytest` — no se despliegan en producción). Las que sí importan porque están directamente en el camino de una petición HTTP real:
  - **`starlette 1.0.0`** (el framework ASGI sobre el que corre FastAPI) — 4 advisories distintas, la más relevante es `PYSEC-2026-161` / `CVE-2026-48710`: Starlette no valida el header `Host` al reconstruir URLs, lo que en aplicaciones que hacen verificaciones basadas en `request.url.path` puede permitir evadir esas verificaciones. Fix: `1.0.1`+.
  - **`cryptography 47.0.0`**, **`urllib3 2.6.3`**, **`h2 4.3.0`**, **`pyjwt 2.12.1`** — parte de la cadena de red usada indirectamente por `httpx`/`supabase-py`.
  - **`pydantic-settings 2.14.1`** (`GHSA-4xgf-cpjx-pc3j`) — investigué esta específicamente: el problema es sobre symlinks en `NestedSecretsSettingsSource` cuando se usa `secrets_nested_subdir=True`. El proyecto **no usa** esa función (`config.py` solo usa `env_file=".env"`), así que esta no es explotable en el estado actual del código, pero el fix es un simple bump de versión sin downside.
- **Recomendación:** correr `pip-audit` como parte de CI (o al menos periódicamente antes de cada release), y priorizar el bump de `starlette`/`fastapi` por ser el más expuesto a tráfico externo.

### 2.5 — [MEDIO] Mensajes de error que exponen rutas internas del servidor

- **Ubicación:** [`backend/app/services/classification_service.py:155-158`](backend/app/services/classification_service.py#L155-L158), propagado sin modificar en [`backend/app/routes/classification.py:17-18`](backend/app/routes/classification.py#L17-L18)
- **Descripción:** cuando falta el índice CPC local, `CpcIndexError` se construye con el **path absoluto completo** del servidor (`f"Falta el artefacto CPC {path}. Ejecute exel/index_cpc_codes.py."`), y la ruta lo reenvía tal cual en el `detail` del HTTP 503. Un cliente externo vería algo como `Falta el artefacto CPC /home/usuario/proyecto/backend/data/cpc_index/titles.csv...`, revelando la estructura de directorios del servidor.
- **Recomendación:** loguear el mensaje completo (con el path) del lado del servidor, y devolver al cliente un mensaje genérico ("El clasificador CPC no está disponible temporalmente") sin el path.

### 2.6 — Investigado y descartado: posible "filter injection" en `PatentService.search()`

- **Ubicación:** [`backend/app/services/patent_service.py:52-59`](backend/app/services/patent_service.py#L52-L59)
- **Descripción:** el código interpola el input del usuario directamente en el string del filtro `or_` de PostgREST, solo escapando la coma manualmente. Antes de reportarlo como vulnerabilidad, lo probé en vivo contra el backend real con inputs diseñados para intentar romper el agrupamiento `or=(...)` o inyectar una condición adicional (`q=)` y `q=zzznomatch).or(id.gt.0`). En ambos casos el resultado fue el esperado para una búsqueda de texto literal (ningún resultado inesperado, ninguna condición adicional colada) — el cliente `postgrest-py` escapa/cita correctamente los valores antes de enviarlos. **No es explotable** con los vectores que probé.
- **Severidad:** solo observación — se documenta para que quede registro de que se investigó activamente y no quedó como sospecha sin verificar.

### 2.7 — Positivo: sin secretos hardcodeados

- Búsqueda de patrones de credenciales (`api_key=`, `secret=`, JWT `eyJ...`, claves `AIza...` de Google) en todos los archivos versionados: sin resultados.
- `.env` nunca fue trackeado por git (confirmado con `git log --all --diff-filter=A -- "**/.env"`, sin resultados) y está correctamente listado en `.gitignore`.
- `backend/.env.example` no contiene valores reales, solo nombres de variable.

### 2.8 — [BAJO] CORS: configuración razonable, pero el valor por defecto no está pensado para producción

- **Ubicación:** [`backend/app/main.py:9-27`](backend/app/main.py#L9-L27), [`backend/app/config.py:8`](backend/app/config.py#L8)
- **Descripción:** la configuración de CORS en sí es correcta — usa un origen fijo (`FRONTEND_ORIGIN`) en vez de `allow_origins=["*"]`, y el regex adicional para redes locales (`10.x`, `172.16-31.x`, `192.168.x`) está bien acotado a rangos privados, no es un wildcard disfrazado. El problema es que `allow_local_network_origins` tiene **`True` como valor por defecto** en `Settings`, y la sección "Despliegue" del README no menciona explícitamente ponerlo en `false` en producción.
- **Recomendación:** agregar una línea en la sección "Despliegue" del README recordando `ALLOW_LOCAL_NETWORK_ORIGINS=false` para entornos de producción (el riesgo real es bajo — CORS solo lo dispara el navegador del cliente, no expone nada del lado servidor por sí solo — pero es una buena práctica de defensa en profundidad).

### 2.9 — [BAJO / PARCIALMENTE RESUELTO (2026-09-11)] Migraciones aplicadas manualmente en el SQL Editor, sin registro en el dashboard de Supabase

- **Ubicación:** `supabase/migrations/*.sql`, dashboard de Supabase (sección "Migrations")
- **Descripción:** confirmado con el equipo — las 4 migraciones existentes se aplicaron copiando/pegando el SQL directamente en el SQL Editor del dashboard, nunca a través del sistema formal de migraciones de Supabase. El dashboard muestra "No migrations" a pesar de que el esquema real sí tiene todos los cambios aplicados. El repositorio era hasta ahora la única fuente de verdad de qué se aplicó.
- **Resolución (parcial):**
  1. Se adoptó el [Supabase CLI](https://supabase.com/docs/guides/local-development), fijado en la versión `2.117.0` como `devDependency` del `package.json` de la raíz, con scripts `db:new` / `db:diff` / `db:push` / `db:list`.
  2. `supabase init` generó `supabase/config.toml` (`project_id = "nextinventia"`).
  3. Las 4 migraciones se movieron de `backend/migrations/` a `supabase/migrations/` con `git mv`, renombradas al formato obligatorio `<YYYYMMDDhhmmss>_<nombre>.sql`:
     - `001_enable_extensions_and_columns.sql` → `20260714092052_enable_extensions_and_columns.sql`
     - `002_hybrid_search_function.sql` → `20260714092053_hybrid_search_function.sql`
     - `003_new_columns_and_unique_pn.sql` → `20260714092054_new_columns_and_unique_pn.sql`
     - `004_rls_policies.sql` → `20260906173200_rls_policies.sql`
  4. El README documenta el flujo nuevo en la sección "Flujo de migraciones (Supabase CLI)".
- **Pendiente (requiere credenciales interactivas, no ejecutable desde el repo):**
  1. `npx supabase login` — autenticación por navegador.
  2. `npx supabase link --project-ref uzwocpslyjbgtugstdmo` — pide la contraseña de Postgres.
  3. `npx supabase migration repair --linked --status applied 20260714092052 20260714092053 20260714092054 20260906173200` — marca las 4 como ya aplicadas. **Solo escribe en `supabase_migrations.schema_migrations`; no re-ejecuta el SQL** ([docs](https://supabase.com/docs/reference/cli/supabase-migration-repair)), lo cual es imprescindible aquí porque el esquema real ya tiene todos esos cambios.
  4. Verificar con `npx supabase migration list --linked` (las 4 deben aparecer en Local y en Remote) y `npx supabase db push --dry-run --linked` (no debe haber nada pendiente).
- **Nota:** hasta completar esos 4 pasos, el dashboard seguirá mostrando "No migrations". La parte versionable del hallazgo (estructura, naming, tooling fijado, documentación) ya está resuelta en el repo.

---

## 3. Calidad y organización del código

### 3.1 — Estructura de carpetas: consistente y clara (observación positiva)

Separación limpia `routes/` → `services/` → `models/` en el backend, y `app/` (páginas) → `components/` → `lib/` en el frontend. `tests/unit/` vs `tests/integration/` también está bien delimitado. No hay nada que reorganizar aquí.

### 3.2 — [MEDIO] Cliente de Supabase creado desde cero en cada request

- **Ubicación:** [`backend/app/dependencies.py:11-12`](backend/app/dependencies.py#L11-L12)
- **Descripción:** `get_supabase()` llama a `create_client(...)` en cada invocación, sin ningún tipo de cacheo/singleton — es una dependencia de FastAPI (`Depends(get_supabase)`) que se resuelve de nuevo en cada petición HTTP a `/patentes/*`. Contrasta con `get_classification_service()`, que sí cachea la instancia en una variable global de módulo.
- **Impacto:** no es incorrecto (cada request obtiene un cliente funcional), pero es trabajo repetido innecesariamente y una inconsistencia de patrón dentro del mismo archivo.
- **Recomendación:** cachear el cliente de Supabase igual que se hace con `ClassificationService`, ya que `supabase-py` no requiere una instancia nueva por request.

### 3.3 — [BAJO] Carga de variables de entorno duplicada en los scripts de `exel/`

- **Ubicación:** [`backend/exel/generate_embeddings.py:21-31`](backend/exel/generate_embeddings.py#L21-L31), [`backend/exel/upload_to_supabase.py:28-38`](backend/exel/upload_to_supabase.py#L28-L38), [`backend/exel/cluster_patentes.py:27-37`](backend/exel/cluster_patentes.py#L27-L37)
- **Descripción:** los 3 scripts repiten idéntico el patrón `load_dotenv(BACKEND_DIR / ".env")` + `os.environ["SUPABASE_URL"]` / `os.environ["SUPABASE_KEY"]`, en paralelo a `app/config.py`, que ya centraliza esto vía pydantic `Settings`. Es una duplicación consciente — estos scripts corren standalone (`python -m exel.xxx`) sin depender del paquete `app` — pero significa que hay 4 lugares distintos leyendo las mismas 2 variables, y un cambio en el nombre de la variable de entorno requeriría actualizar 4 archivos en vez de 1.
- **Recomendación (opcional, bajo impacto):** si se quiere mantener la independencia de los scripts, está bien dejarlo así; si no, podrían importar `app.config.settings` directamente ya que igualmente corren dentro del mismo virtualenv del backend.

### 3.4 — [BAJO] Manejo de errores inconsistente en el frontend (`lib/api.ts`)

- **Ubicación:** [`frontend/src/lib/api.ts:101-181`](frontend/src/lib/api.ts#L101-L181)
- **Descripción:** `fetchPatents`, `fetchPatentById`, `searchSemantic` y `fetchSimilarPatents` lanzan un `Error` genérico (`` `Error ${res.status}` ``) sin leer el cuerpo de la respuesta. Solo `recommendCpcCodes` parsea el campo `detail` que el backend sí envía, para mostrar un mensaje útil al usuario. No hay una razón visible para la diferencia — probablemente `recommendCpcCodes` se escribió después y adoptó una mejor práctica que no se retro-aplicó a las demás.
- **Recomendación:** unificar en una función helper (`parseApiError(res)`) que todas las funciones de `api.ts` reutilicen.

### 3.5 — Naming: consistente, sin mezcla arbitraria de idiomas (observación positiva)

Revisé specificamente si había mezcla español/inglés sin criterio. No la encontré: los nombres de columnas de dominio (`descripcion`, `claimen`, `patentes`) están en español porque reflejan literalmente columnas de la base de datos real; identificadores de código (clases, funciones, variables) están en inglés; docstrings y comentarios explicativos están en español. Es un criterio aplicado consistentemente en todo el proyecto, no una mezcla accidental.

---

## 4. Rendimiento y optimización

### 4.1 — [MEDIO] `generate_embeddings.py` sigue haciendo un `UPDATE` por patente (ya identificado por el equipo, confirmado vigente)

- **Ubicación:** [`backend/exel/generate_embeddings.py:79-81`](backend/exel/generate_embeddings.py#L79-L81), [`backend/exel/generate_embeddings.py:110-120`](backend/exel/generate_embeddings.py#L110-L120)
- **Descripción:** la generación del embedding en sí **ya está bien batcheada** (`model.encode(texts, batch_size=64, ...)` una vez por página de 200 filas) — este script no tiene el problema de "un `encode()` por patente" que originalmente se pensó que tenía. El cuello de botella real y vigente es distinto: `update_embedding()` hace un `UPDATE ... WHERE id = :id` **individual por cada fila** dentro del loop principal, en vez de agrupar por chunks como sí hace `cluster_patentes.py` (`update_clusters`, ~100 ids por request) o `upload_to_supabase.py` (batch `insert`).
- **Recomendación:** aplicar el mismo patrón que ya usa `cluster_patentes.py`: agrupar los `(id, vector)` en chunks y hacer upsert por lote en vez de un `UPDATE` por fila. Esto ya está marcado como "en progreso" según la conversación con el equipo — se confirma aquí que sigue pendiente en el código actual de `develop`.

### 4.2 — [BAJO] Dos round-trips secuenciales en `get_all()` y `search()`

- **Ubicación:** [`backend/app/services/patent_service.py:17-31`](backend/app/services/patent_service.py#L17-L31) y `:43-78`
- **Descripción:** cada llamada hace una consulta para el `count` y otra para los datos paginados — dos idas y vueltas a Supabase por cada petición de listado/búsqueda. No es un N+1 real (no crece con el número de filas), pero sí es una oportunidad de reducir latencia si se quisiera exprimir más el endpoint más usado de la API.
- **Recomendación:** bajo impacto, no urgente. Si se optimiza, la opción más limpia sería una función RPC que devuelva `count` + `data` en una sola llamada, similar a como ya se hizo con `search_patentes_hybrid`.

### 4.3 — Positivo: la cascada de Gemini + rate limiting ya se usa de forma consistente

Confirmé leyendo ambos archivos en `develop` que **tanto** `classification_service.py` **como** `chat.py` usan `GeminiFallbackClient` (cascada de 3 modelos + rate limiting real). La inconsistencia que existía anteriormente (`chat.py` con un `genai.Client` fijo a un solo modelo y su propio retry manual) ya fue corregida — no hay ningún lugar del código que llame a Gemini por fuera de `GeminiFallbackClient`.

### 4.4 — Ver también 3.2 (cliente de Supabase sin reuso por request)

Aplica tanto a calidad de código como a rendimiento — se documenta una sola vez en la sección 3 para no duplicar el hallazgo.

---

## 5. Configuración y variables de entorno

### 5.1 — Variables requeridas (todas documentadas)

| Variable | Requerida | Default | Documentada en README | Documentada en `.env.example` |
|---|---|---|---|---|
| `SUPABASE_URL` | Sí | — | Sí | Sí |
| `SUPABASE_KEY` | Sí | — | Sí | Sí |
| `GEMINI_API_KEY` | Sí | — | Sí | Sí |
| `FRONTEND_ORIGIN` | No | `http://localhost:3000` | Sí | Sí |
| `ALLOW_LOCAL_NETWORK_ORIGINS` | No | `true` | Sí (sección "Uso en red local") | **No** |
| `NEXT_PUBLIC_API_URL` (frontend) | No | `http://localhost:8000` | Sí | No aplica (no hay `.env.example` en frontend) |

### 5.2 — [BAJO] `ALLOW_LOCAL_NETWORK_ORIGINS` falta en `backend/.env.example`

- **Ubicación:** [`backend/.env.example`](backend/.env.example)
- **Descripción:** la variable existe en `config.py` con default `True` y está documentada en prosa en el README, pero no aparece (ni siquiera comentada) en el `.env.example`, que es el primer lugar donde un desarrollador nuevo mira para saber qué puede configurar.
- **Recomendación:** agregar `# ALLOW_LOCAL_NETWORK_ORIGINS=true` (comentado, con el default explícito) al `.env.example`.

### 5.3 — [BAJO] Falta `.env.local.example` en el frontend

- **Ubicación:** `frontend/` (archivo ausente)
- **Descripción:** `NEXT_PUBLIC_API_URL` está bien documentado en el README, pero no hay un archivo de ejemplo versionado en `frontend/`, a diferencia del backend que sí tiene `backend/.env.example`.
- **Recomendación:** agregar `frontend/.env.local.example` con `NEXT_PUBLIC_API_URL=http://localhost:8000`.

---

## Resumen de hallazgos por severidad

_Actualizado 2026-09-06 tras resolver 2.2 (ver esa sección para el detalle de la resolución)._

| Severidad | Cantidad | Resueltos |
|---|---|---|
| Crítico | 0 | 0 |
| Alto | 4 | 1 (2.2) |
| Medio | 6 | 0 |
| Bajo | 9 | 0 |
| Solo observación (incluye positivos) | 6 | — |
| **Total** | **25** | **1** |

## Top 5 a resolver primero

_Lista original de la auditoría (2026-08-21), actualizada: 2.2 se resolvió y sale de esta lista; sube 2.4 en su lugar._

1. **[1.1 — Alto]** `GET /patentes/{id}` devuelve 500 en vez de 404 para ids inexistentes — confirmado en vivo, afecta a cualquier usuario que llegue a un enlace roto o escriba mal un id. Fix acotado (un `try/except` en `patent_service.py`).
2. **[2.1 — Alto]** Agregar rate limiting básico a `/chat/` y `/clasificacion/cpc/recommend` — hoy cualquiera puede generar costo ilimitado en la cuenta de Gemini del equipo.
3. **[2.3 — Alto]** Actualizar Next.js a `16.3.4`+ — 4 vulnerabilidades de severidad alta con fix ya disponible, incluyendo divulgación no autenticada de endpoints internos.
4. **[1.2 — Medio]** Cubrir con tests `search_semantic` y `get_similares` antes de seguir construyendo funcionalidad nueva encima de ellos (especialmente relevante si el "funnel" de búsqueda global que se está diseñando va a apoyarse en este mismo servicio).
5. **[2.4 — Medio]** Actualizar `starlette` (y de paso `fastapi`) — es el framework ASGI directamente expuesto a tráfico externo, con una vulnerabilidad de validación de header `Host` (`CVE-2026-48710`) entre las 4 detectadas por `pip-audit`.

✅ **Resuelto desde la versión original de este documento:** ~~2.2 — RLS sin versionar~~ (ver sección 2.2 para el detalle completo).
