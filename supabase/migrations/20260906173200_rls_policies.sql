-- =============================================================================
-- Migración 004: Row Level Security (RLS) en `patentes`
-- =============================================================================
-- Contexto (ver AUDITORIA.md, hallazgo 2.2):
--
--   Hasta ahora RLS se administraba manualmente desde el SQL Editor del
--   dashboard de Supabase, sin versionar en el repositorio. El estado
--   encontrado antes de esta migración (confirmado en el dashboard, no
--   deducido) era:
--
--     - RLS habilitado en `patentes`.
--     - 3 políticas para el rol `anon`:
--         "Allow public read access"   (SELECT)
--         "Allow public update access" (UPDATE)
--         "Allow all access"           (ALL)
--
--   Es decir, la `anon key` — la misma que usa el backend de producción
--   (app/dependencies.py) — podía escribir y borrar libremente sobre
--   `patentes` directamente vía la REST API de Supabase, sin pasar por
--   FastAPI. El backend de producción solo necesita leer.
--
-- Cambio aplicado (y que esta migración versiona):
--
--   Se eliminaron las 3 políticas anteriores y se dejó una sola:
--   `anon` con permiso de SELECT únicamente. Toda la escritura
--   (backend/exel/upload_to_supabase.py, generate_embeddings.py,
--   cluster_patentes.py) ya fue migrada para usar `SUPABASE_SERVICE_ROLE_KEY`
--   en vez de la anon key — esa key bypassa RLS por diseño, así que estos
--   scripts no se ven afectados por esta restricción.
--
-- Verificado en vivo tras el cambio: GET /patentes/, GET /patentes/{id},
-- POST /patentes/search/semantic (RPC search_patentes_hybrid) y
-- GET /patentes/{id}/similares (RPC patentes_similares) siguen respondiendo
-- 200 — ninguno de los dos RPC necesita escribir, así que no se rompen.
--
-- Nota pendiente (no se resuelve en esta migración): las funciones RPC
-- (migración 002) están declaradas `SECURITY INVOKER` (default, sin
-- `SECURITY DEFINER`), por lo que corren con los privilegios del rol que
-- llama. El `GRANT EXECUTE` de la migración 002 incluye a `authenticated`
-- además de `anon`, pero esta migración no crea ninguna política de SELECT
-- para `authenticated` sobre `patentes`. Hoy no tiene efecto práctico
-- (la app no autentica usuarios vía Supabase Auth), pero si en el futuro se
-- agrega login, un usuario `authenticated` real obtendría 0 filas al llamar
-- estos RPC hasta que se agregue una política de SELECT equivalente para ese
-- rol.
--
-- Idempotente: usa DROP POLICY IF EXISTS antes de crear, así que se puede
-- correr sobre una base ya migrada sin error. Si se corre sobre un proyecto
-- de Supabase nuevo (sin las políticas legacy), los DROP simplemente no
-- hacen nada y el resultado final es el mismo.
-- Pre-requisito: haber corrido las migraciones 001, 002 y 003.
-- =============================================================================

ALTER TABLE patentes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow public read access" ON patentes;
DROP POLICY IF EXISTS "Allow public update access" ON patentes;
DROP POLICY IF EXISTS "Allow all access" ON patentes;

CREATE POLICY "Allow public read access"
ON patentes FOR SELECT TO anon USING (true);
