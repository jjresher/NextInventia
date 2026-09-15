-- =============================================================================
-- Migración 001: Habilitar búsqueda híbrida (BM25 + Semántica) sobre `patentes`
-- =============================================================================
-- Activa las extensiones necesarias y agrega las columnas/índices que soportan:
--   * Búsqueda léxica  (Postgres FTS, similar a BM25) -> columna `search_vector`
--   * Búsqueda semántica (Sentence-BERT + KNN)        -> columna `embedding`
--   * Clustering K-means para "patentes similares"    -> columna `cluster_id`
--
-- Idempotente: se puede correr varias veces sin error.
-- =============================================================================

-- 1) Extensiones --------------------------------------------------------------
-- `vector`  : tipo de dato vector + índices HNSW/IVFFlat (pgvector).
-- `pg_trgm` : índices de trigramas para fuzzy match de strings cortos
--             (útil para que números de patente o siglas CPC se encuentren
--             aún con pequeños typos: 'US10123456' vs 'US 10123456').
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 2) Columnas nuevas ----------------------------------------------------------

-- 2.1) `search_vector`: tsvector generado automáticamente a partir de los
-- campos textuales, con pesos:
--   A = título      (más relevante)
--   B = abstract
--   C = descripción
--   D = claims      (menos relevante, suele ser muy largo)
--
-- Se usa la configuración 'simple' porque el corpus mezcla ES y EN; usar
-- 'english' aplicaría stemming inglés que deformaría palabras en español.
ALTER TABLE patentes
  ADD COLUMN IF NOT EXISTS search_vector tsvector
  GENERATED ALWAYS AS (
    setweight(to_tsvector('simple', coalesce(ti,'')),          'A') ||
    setweight(to_tsvector('simple', coalesce(ab,'')),          'B') ||
    setweight(to_tsvector('simple', coalesce(descripcion,'')), 'C') ||
    setweight(to_tsvector('simple', coalesce(claimen,'')),     'D')
  ) STORED;

-- 2.2) `embedding`: vector denso de 384 dimensiones que produce el modelo
-- `paraphrase-multilingual-MiniLM-L12-v2`.
-- Se permite NULL para poder ir poblándolo gradualmente desde el script de
-- indexación sin romper inserts existentes.
ALTER TABLE patentes
  ADD COLUMN IF NOT EXISTS embedding vector(384);

-- 2.3) `cluster_id`: id del cluster asignado por K-means (Fase 5).
-- También nullable porque se calcula offline después de generar embeddings.
ALTER TABLE patentes
  ADD COLUMN IF NOT EXISTS cluster_id integer;

-- 3) Índices ------------------------------------------------------------------

-- 3.1) GIN sobre `search_vector` -> búsquedas FTS rápidas (`@@`).
CREATE INDEX IF NOT EXISTS idx_patentes_fts
  ON patentes USING GIN (search_vector);

-- 3.2) HNSW sobre `embedding` con distancia coseno -> KNN semántico.
-- m=16 y ef_construction=64 son los valores por defecto recomendados por
-- pgvector para datasets de hasta cientos de miles de filas.
CREATE INDEX IF NOT EXISTS idx_patentes_embedding
  ON patentes USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- 3.3) Trigramas sobre `pn` -> permite buscar números de patente con typos
-- y soporta `ILIKE '%...%'` con índice (ya no full scan).
CREATE INDEX IF NOT EXISTS idx_patentes_pn_trgm
  ON patentes USING GIN (pn gin_trgm_ops);

-- 3.4) Btree sobre `cluster_id` -> filtros rápidos por cluster.
CREATE INDEX IF NOT EXISTS idx_patentes_cluster
  ON patentes (cluster_id);

-- 4) Verificación rápida ------------------------------------------------------
-- Después de ejecutar este script puedes correr:
--   SELECT count(*) FROM patentes WHERE search_vector IS NOT NULL;  -- = total
--   SELECT count(*) FROM patentes WHERE embedding IS NOT NULL;      -- = 0 (aún)
-- y en Database > Indexes deben aparecer los 4 índices nuevos.
