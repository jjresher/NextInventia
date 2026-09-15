-- =============================================================================
-- Row Level Security (RLS) en `patentes`
-- =============================================================================
-- Contexto (ver AUDITORIA_CODIGO.md, R-04; issue #24):
--
--   RLS se administraba a mano desde el SQL Editor del dashboard, sin quedar
--   versionado. El estado encontrado antes de este cambio (leído del
--   dashboard, no deducido) era:
--
--     - RLS habilitado en `patentes`.
--     - 3 políticas para el rol `anon`:
--         "Allow public read access"   (SELECT)
--         "Allow public update access" (UPDATE)
--         "Allow all access"           (ALL)
--
--   Es decir, la anon key —la misma que usa el backend— podía escribir y
--   borrar sobre `patentes` vía la REST API de Supabase, sin pasar por
--   FastAPI. El backend solo necesita leer.
--
-- Cambio aplicado a mano en el dashboard y que este archivo versiona de forma
-- retroactiva: se eliminaron las 3 políticas y quedó solo SELECT para `anon`.
-- La escritura vive en los procesos de backend/exel/, que desde #51 usan
-- SUPABASE_SERVICE_ROLE_KEY; esa key bypassea RLS por diseño, así que no se
-- ven afectados.
--
-- Estado remoto confirmado el 15/09/2026, antes de versionar este archivo:
--
--     SELECT policyname, roles, cmd, qual FROM pg_policies
--     WHERE tablename = 'patentes';
--     -- "Allow public read access" | {anon} | SELECT | true   (fila única)
--
--     SELECT relrowsecurity FROM pg_class WHERE relname = 'patentes';
--     -- true
--
--   La base remota ya coincide con el resultado de este archivo, así que se
--   marca como aplicada con `supabase migration repair --status applied` en
--   vez de ejecutarse. Su valor es que un proyecto nuevo reproduzca la misma
--   postura, y que el repo explique por qué el remoto no coincide con lo que
--   generan las migraciones anteriores.
--
-- Nota pendiente (no se resuelve aquí): las funciones RPC están declaradas
-- SECURITY INVOKER, así que corren con los privilegios de quien llama. El
-- GRANT EXECUTE incluye a `authenticated`, pero no existe política de SELECT
-- para ese rol sobre `patentes` —confirmado en la consulta de arriba, donde
-- la única política es de `anon`—. Hoy no tiene efecto práctico porque la app
-- no usa Supabase Auth, pero si se agrega login, un usuario `authenticated`
-- obtendrá 0 filas hasta que se cree la política equivalente.
--
-- Idempotente: los DROP usan IF EXISTS y sobre el remoto actual solo eliminan
-- y recrean la política de lectura, dejando el mismo estado final.
-- Pre-requisito: las migraciones 20260714092052 a 20260714092055.
-- =============================================================================

ALTER TABLE patentes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow public read access" ON patentes;
DROP POLICY IF EXISTS "Allow public update access" ON patentes;
DROP POLICY IF EXISTS "Allow all access" ON patentes;

CREATE POLICY "Allow public read access"
ON patentes FOR SELECT TO anon USING (true);
