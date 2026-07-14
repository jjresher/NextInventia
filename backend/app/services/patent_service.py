from supabase import Client

from app.services.embedding_service import encode_query

# Columnas devueltas en listados/búsquedas. Incluye los nombres "nuevos"
# (apc, ww, pd, lg_st) y mantiene los legacy (pc, ws, ls) por compat con
# datos antiguos que aún no fueron re-procesados.
SUMMARY_COLUMNS = (
    "id,pn,apc,cpc,ic,ww,pd,lg_st,ti,ab,espacenet,cluster_id,"
    "pc,ws,ls"
)
ALL_COLUMNS = "*"


class PatentService:
    def __init__(self, client: Client):
        self._client = client
        self._table = "patentes"

    def get_all(self, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        offset = (page - 1) * page_size

        count_resp = self._client.table(self._table).select("id", count="exact").execute()
        total = count_resp.count or 0

        data_resp = (
            self._client.table(self._table)
            .select(SUMMARY_COLUMNS)
            .order("id")
            .range(offset, offset + page_size - 1)
            .execute()
        )

        return data_resp.data, total

    def get_by_id(self, patent_id: int) -> dict | None:
        resp = (
            self._client.table(self._table)
            .select(ALL_COLUMNS)
            .eq("id", patent_id)
            .single()
            .execute()
        )
        return resp.data

    def search(self, query: str, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        """Búsqueda léxica simple con ILIKE. Se mantiene como fallback rápido
        para usuarios que solo quieren matchear un número de patente, palabra
        clave exacta, nombre de empresa o categoría temática sin pagar el
        coste del embedding."""
        offset = (page - 1) * page_size

        # Sanitizamos: en PostgREST el separador es la coma, así que cualquier
        # coma del usuario rompería el `or_`.
        safe = query.replace(",", " ")
        or_filter = (
            f"ti.ilike.%{safe}%,"
            f"ab.ilike.%{safe}%,"
            f"pn.ilike.%{safe}%,"
            f"ww.ilike.%{safe}%,"
            f"apc.ilike.%{safe}%"
        )

        count_resp = (
            self._client.table(self._table)
            .select("id", count="exact")
            .or_(or_filter)
            .execute()
        )
        total = count_resp.count or 0

        data_resp = (
            self._client.table(self._table)
            .select(SUMMARY_COLUMNS)
            .or_(or_filter)
            .order("id")
            .range(offset, offset + page_size - 1)
            .execute()
        )

        return data_resp.data, total

    def search_semantic(self, query: str, top_k: int = 20) -> list[dict]:
        """Búsqueda híbrida BM25 + Sentence-BERT con fusión RRF.

        Llama al RPC `search_patentes_hybrid` definido en
        `migrations/002_hybrid_search_function.sql`.
        """
        query_embedding = encode_query(query)
        resp = self._client.rpc(
            "search_patentes_hybrid",
            {
                "query_text": query,
                "query_embedding": query_embedding,
                "top_k": top_k,
            },
        ).execute()
        return resp.data or []

    def get_similares(self, patent_id: int, top_k: int = 10) -> list[dict]:
        """KNN puro sobre el embedding de la patente dada. Devuelve las
        `top_k` patentes más cercanas (excluyendo la propia)."""
        resp = self._client.rpc(
            "patentes_similares",
            {"patent_id": patent_id, "top_k": top_k},
        ).execute()
        return resp.data or []
