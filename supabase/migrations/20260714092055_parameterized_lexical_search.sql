-- Búsqueda léxica parametrizada para GET /patentes/?q=.
-- El texto del usuario se recibe como argumento SQL y nunca se concatena en la
-- gramática de filtros de PostgREST. %, _ y \ se escapan para que la consulta
-- se interprete literalmente.

CREATE OR REPLACE FUNCTION public.search_patentes_lexical(
    query_text          text,
    requested_page      integer DEFAULT 1,
    requested_page_size integer DEFAULT 50
)
RETURNS jsonb
LANGUAGE sql STABLE
SET search_path = ''
AS $$
    WITH params AS (
        SELECT replace(
            replace(
                replace(btrim(query_text), E'\\', E'\\\\'),
                '%', E'\\%'
            ),
            '_', E'\\_'
        ) AS escaped_query
        WHERE char_length(btrim(query_text)) BETWEEN 1 AND 200
    ),
    filtered AS (
        SELECT
            p.id, p.pn, p.apc, p.cpc, p.ic, p.ww, p.pd, p.lg_st,
            p.ti, p.ab, p.espacenet, p.cluster_id
        FROM public.patentes AS p
        CROSS JOIN params
        WHERE coalesce(p.ti, '') ILIKE '%' || params.escaped_query || '%' ESCAPE '\'
           OR coalesce(p.ab, '') ILIKE '%' || params.escaped_query || '%' ESCAPE '\'
           OR coalesce(p.pn, '') ILIKE '%' || params.escaped_query || '%' ESCAPE '\'
           OR coalesce(p.ww, '') ILIKE '%' || params.escaped_query || '%' ESCAPE '\'
           OR coalesce(p.apc, '') ILIKE '%' || params.escaped_query || '%' ESCAPE '\'
    ),
    page_rows AS (
        SELECT *
        FROM filtered
        ORDER BY id
        OFFSET (greatest(requested_page, 1) - 1)::bigint
            * least(greatest(requested_page_size, 1), 200)
        LIMIT least(greatest(requested_page_size, 1), 200)
    )
    SELECT jsonb_build_object(
        'data', coalesce(
            (SELECT jsonb_agg(to_jsonb(page_rows) ORDER BY id) FROM page_rows),
            '[]'::jsonb
        ),
        'count', (SELECT count(*) FROM filtered)
    );
$$;

REVOKE ALL ON FUNCTION public.search_patentes_lexical(text, integer, integer)
    FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.search_patentes_lexical(text, integer, integer)
    TO anon, authenticated;
