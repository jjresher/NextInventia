-- =============================================================================
-- Migración 002: Función `search_patentes_hybrid` (BM25 + Semántica + RRF)
-- =============================================================================
-- Combina dos rankings independientes:
--   * Léxico   -> Postgres FTS sobre `search_vector` (similar a BM25).
--   * Semántico-> KNN con pgvector sobre `embedding` (Sentence-BERT).
-- Y los fusiona con Reciprocal Rank Fusion (RRF), que pondera POSICIONES, no
-- scores absolutos (que son incomparables entre BM25 y coseno).
--
-- Fórmula: RRF(doc) = Σ_i 1 / (k + rank_i(doc))   con k=60 (estándar).
--
-- Uso desde el cliente:
--   supabase.rpc(
--     "search_patentes_hybrid",
--     {
--       "query_text": "vehículo autónomo",
--       "query_embedding": [0.012, -0.034, ...],   # 384 floats
--       "top_k": 20
--     }
--   )
-- =============================================================================

-- Si la firma cambió respecto a una versión anterior (p.ej. al pasar de
-- pc/ws/ls -> apc/ww/lg_st/pd), hay que dropear primero porque
-- CREATE OR REPLACE no permite cambiar las columnas devueltas.
DROP FUNCTION IF EXISTS search_patentes_hybrid(text, vector, integer, integer, integer);

CREATE OR REPLACE FUNCTION search_patentes_hybrid(
    query_text      text,
    query_embedding vector(384),
    top_k           integer DEFAULT 20,
    candidate_pool  integer DEFAULT 50,
    rrf_k           integer DEFAULT 60
)
RETURNS TABLE (
    id         bigint,
    pn         text,
    apc        text,
    cpc        text,
    ic         text,
    ww         text,
    lg_st      text,
    pd         text,
    ti         text,
    ab         text,
    espacenet  text,
    cluster_id integer,
    rrf_score  double precision,
    fts_rank   integer,
    sem_rank   integer
)
LANGUAGE sql STABLE
AS $$
    WITH
    -- 1) Top candidatos léxicos (FTS).
    --    `websearch_to_tsquery` tolera input libre tipo "carro autónomo"
    --    sin que el usuario tenga que escribir sintaxis con operadores.
    --    Se llama inline (en lugar de aliasarla en el FROM) porque la
    --    función es IMMUTABLE y Postgres la evalúa una sola vez en el plan;
    --    aliasarla con `AS q(query)` también funcionaría, pero inline es
    --    más portable entre versiones de PostgREST/Supabase.
    fts AS (
        SELECT
            p.id,
            ROW_NUMBER() OVER (
                ORDER BY ts_rank_cd(
                    p.search_vector,
                    websearch_to_tsquery('simple', query_text)
                ) DESC
            )::int AS r
        FROM patentes p
        WHERE p.search_vector @@ websearch_to_tsquery('simple', query_text)
        LIMIT candidate_pool
    ),
    -- 2) Top candidatos semánticos (KNN coseno).
    sem AS (
        SELECT
            p.id,
            ROW_NUMBER() OVER (
                ORDER BY p.embedding <=> query_embedding
            )::int AS r
        FROM patentes p
        WHERE p.embedding IS NOT NULL
        ORDER BY p.embedding <=> query_embedding
        LIMIT candidate_pool
    ),
    -- 3) Fusión RRF: cualquier doc presente en alguno de los dos rankings.
    fused AS (
        SELECT
            COALESCE(fts.id, sem.id) AS id,
            fts.r                    AS fts_rank,
            sem.r                    AS sem_rank,
            (
                CASE WHEN fts.r IS NOT NULL
                     THEN 1.0 / (rrf_k + fts.r) ELSE 0 END
              + CASE WHEN sem.r IS NOT NULL
                     THEN 1.0 / (rrf_k + sem.r) ELSE 0 END
            ) AS rrf_score
        FROM fts
        FULL OUTER JOIN sem ON sem.id = fts.id
    )
    SELECT
        p.id, p.pn, p.apc, p.cpc, p.ic, p.ww, p.lg_st, p.pd,
        p.ti, p.ab, p.espacenet, p.cluster_id,
        f.rrf_score,
        f.fts_rank,
        f.sem_rank
    FROM fused f
    JOIN patentes p ON p.id = f.id
    ORDER BY f.rrf_score DESC
    LIMIT top_k;
$$;

-- Permitir que el cliente anónimo (anon key) llame al RPC.
GRANT EXECUTE ON FUNCTION search_patentes_hybrid(text, vector, integer, integer, integer)
    TO anon, authenticated;

-- =============================================================================
-- Función auxiliar para "patentes similares" (KNN puro sobre embedding).
-- =============================================================================
DROP FUNCTION IF EXISTS patentes_similares(bigint, integer);

CREATE OR REPLACE FUNCTION patentes_similares(
    patent_id bigint,
    top_k     integer DEFAULT 10
)
RETURNS TABLE (
    id         bigint,
    pn         text,
    ti         text,
    ab         text,
    ww         text,
    apc        text,
    cluster_id integer,
    distance   double precision
)
LANGUAGE sql STABLE
AS $$
    WITH base AS (
        SELECT embedding FROM patentes WHERE id = patent_id
    )
    SELECT
        p.id, p.pn, p.ti, p.ab, p.ww, p.apc, p.cluster_id,
        (p.embedding <=> (SELECT embedding FROM base)) AS distance
    FROM patentes p, base
    WHERE p.id <> patent_id
      AND p.embedding IS NOT NULL
      AND base.embedding IS NOT NULL
    ORDER BY p.embedding <=> (SELECT embedding FROM base)
    LIMIT top_k;
$$;

GRANT EXECUTE ON FUNCTION patentes_similares(bigint, integer)
    TO anon, authenticated;
