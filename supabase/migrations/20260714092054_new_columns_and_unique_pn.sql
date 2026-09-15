-- =============================================================================
-- Migración 003: Esquema actualizado para los nuevos exports de Patentologos
-- =============================================================================
-- Cambios respecto al esquema original:
--
--   * Se añaden 4 columnas nuevas que vienen en los exports recientes:
--       - apc   (applicant company)
--       - pd    (publication date, formato libre tipo 'YYYY-MM-DD')
--       - ww    (categoría temática granular: "Electrical engineering/...")
--       - lg_st (legal status)
--
--   * Las columnas legacy `ws` y `ls` se mantienen para no romper datos
--     históricos, pero se hace BACKFILL hacia `ww` y `lg_st` para que la
--     búsqueda y los filtros usen un único nombre de aquí en adelante.
--
--   * `pn` (patent number) pasa a ser UNIQUE: es la clave natural y permite
--     que el script de carga use UPSERT (`on_conflict="pn"`) para no
--     insertar duplicados.
--
--   * Se reconstruye `search_vector` para que el índice FTS también pondere
--     la categoría temática (`ww`) y el solicitante (`apc`). Eso hace que
--     buscar "wind turbine" o el nombre de una empresa funcione tanto por
--     léxico (BM25) como por semántica.
--
-- Idempotente: se puede ejecutar varias veces sin error.
-- Pre-requisito: haber corrido las migraciones 001 y 002 al menos una vez.
-- =============================================================================

-- 1) Columnas nuevas ----------------------------------------------------------
ALTER TABLE patentes ADD COLUMN IF NOT EXISTS apc   text;
ALTER TABLE patentes ADD COLUMN IF NOT EXISTS pd    text;
ALTER TABLE patentes ADD COLUMN IF NOT EXISTS ww    text;
ALTER TABLE patentes ADD COLUMN IF NOT EXISTS lg_st text;

-- 2) Backfill desde columnas legacy hacia las nuevas --------------------------
-- Solo si la nueva está vacía y la antigua tiene dato (no pisamos cargas
-- nuevas si ya se subió algo con el script actualizado).
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'patentes' AND column_name = 'ws'
  ) THEN
    EXECUTE 'UPDATE patentes
             SET ww = ws
             WHERE ww IS NULL
               AND ws IS NOT NULL
               AND ws <> ''''';
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'patentes' AND column_name = 'ls'
  ) THEN
    EXECUTE 'UPDATE patentes
             SET lg_st = ls
             WHERE lg_st IS NULL
               AND ls IS NOT NULL
               AND ls <> ''''';
  END IF;
END$$;

-- 3) Deduplicar pn antes de aplicar el UNIQUE ---------------------------------
-- Si por alguna ejecución anterior del script viejo (que solo hacía INSERT)
-- quedaron filas con el mismo `pn`, conservamos la de mayor `id` (la más
-- reciente) y borramos las demás. Sin esto, la siguiente sentencia falla.
DELETE FROM patentes a
USING patentes b
WHERE a.id < b.id
  AND a.pn = b.pn
  AND a.pn IS NOT NULL;

-- 4) Constraint UNIQUE sobre pn -----------------------------------------------
-- El backend usará `upsert(..., on_conflict="pn")`, que requiere unicidad.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'patentes_pn_unique'
  ) THEN
    ALTER TABLE patentes
      ADD CONSTRAINT patentes_pn_unique UNIQUE (pn);
  END IF;
END$$;

-- 5) Reconstruir search_vector para incluir ww + apc --------------------------
-- `search_vector` es una columna GENERATED ALWAYS, así que para cambiarle la
-- expresión hay que dropear (con el índice GIN que la usa) y volver a crear.
-- La regeneración es automática y rápida en datasets de < 100 k filas.
DROP INDEX IF EXISTS idx_patentes_fts;
ALTER TABLE patentes DROP COLUMN IF EXISTS search_vector;

ALTER TABLE patentes
  ADD COLUMN search_vector tsvector
  GENERATED ALWAYS AS (
    setweight(to_tsvector('simple', coalesce(ti,'')),          'A') ||
    setweight(to_tsvector('simple', coalesce(ab,'')),          'B') ||
    setweight(to_tsvector('simple', coalesce(ww,'')),          'B') ||
    setweight(to_tsvector('simple', coalesce(apc,'')),         'C') ||
    setweight(to_tsvector('simple', coalesce(descripcion,'')), 'C') ||
    setweight(to_tsvector('simple', coalesce(claimen,'')),     'D')
  ) STORED;

CREATE INDEX idx_patentes_fts
  ON patentes USING GIN (search_vector);

-- 6) Índices auxiliares para las columnas nuevas ------------------------------
-- 6.1) Btree sobre `pd` para ordenar por fecha y filtros por rango.
CREATE INDEX IF NOT EXISTS idx_patentes_pd
  ON patentes (pd);

-- 6.2) Trigramas sobre `ww` y `apc` para fuzzy / ILIKE rápido (búsqueda por
-- categoría o por empresa con typos).
CREATE INDEX IF NOT EXISTS idx_patentes_ww_trgm
  ON patentes USING GIN (ww gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_patentes_apc_trgm
  ON patentes USING GIN (apc gin_trgm_ops);

-- 7) Verificación rápida ------------------------------------------------------
-- SELECT count(*) FROM patentes;
-- SELECT count(*) FROM patentes WHERE search_vector IS NOT NULL;  -- = total
-- SELECT count(*) FROM patentes WHERE ww IS NOT NULL;             -- viejos+nuevos
-- SELECT count(*) FROM patentes WHERE apc IS NOT NULL;            -- solo nuevos
-- SELECT count(*) FROM patentes WHERE pd  IS NOT NULL;            -- solo nuevos
-- SELECT conname FROM pg_constraint WHERE conname = 'patentes_pn_unique';
