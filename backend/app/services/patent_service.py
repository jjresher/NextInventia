from supabase import Client

from app.services.embedding_service import encode_query

# Columnas devueltas en listados/búsquedas.
SUMMARY_COLUMNS = (
    "id,pn,apc,cpc,ic,ww,pd,lg_st,ti,ab,espacenet,cluster_id"
)
ALL_COLUMNS = "*"


class PatentService:
    def __init__(self, client: Client):
        self._client = client
        self._table = "patentes"

    def get_all(self, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        offset = (page - 1) * page_size
        response = (
            self._client.table(self._table)
            .select(SUMMARY_COLUMNS, count="exact")
            .order("id")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        return response.data or [], response.count or 0

    def get_by_id(self, patent_id: int) -> dict | None:
        resp = (
            self._client.table(self._table)
            .select(ALL_COLUMNS)
            .eq("id", patent_id)
            .maybe_single()
            .execute()
        )
        return resp.data

    def get_by_ids(self, patent_ids: list[int]) -> list[dict]:
        """Obtiene patentes completas conservando el orden solicitado."""
        if not patent_ids:
            return []
        columns = ALL_COLUMNS if len(patent_ids) == 1 else SUMMARY_COLUMNS
        resp = (
            self._client.table(self._table)
            .select(columns)
            .in_("id", patent_ids)
            .execute()
        )
        by_id = {row.get("id"): row for row in (resp.data or [])}
        return [by_id[item] for item in patent_ids if item in by_id]

    def search(self, query: str, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        """Búsqueda léxica parametrizada, sin interpolar texto en filtros.

        La RPC aplica ILIKE literal sobre los campos de resumen y devuelve datos
        y conteo en una sola llamada. Sus límites también protegen a clientes que
        invoquen PostgREST sin pasar por la validación de FastAPI.
        """
        resp = self._client.rpc(
            "search_patentes_lexical",
            {
                "query_text": query,
                "requested_page": page,
                "requested_page_size": page_size,
            },
        ).execute()
        result = resp.data or {}
        return result.get("data", []), result.get("count", 0)

    def search_semantic(self, query: str, top_k: int = 20) -> list[dict]:
        """Búsqueda híbrida PostgreSQL FTS + Sentence-BERT con fusión RRF.

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
