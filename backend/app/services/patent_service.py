import time
from collections.abc import Callable
from typing import Any

import httpx
from supabase import Client

from app.errors import ExternalServiceTimeoutError
from app.observability import NULL_METRICS, MetricsRegistry
from app.services.embedding_service import encode_query

# Columnas devueltas en listados/búsquedas.
SUMMARY_COLUMNS = (
    "id,pn,apc,cpc,ic,ww,pd,lg_st,ti,ab,espacenet,cluster_id"
)
ALL_COLUMNS = "*"


class PatentService:
    def __init__(
        self,
        client: Client,
        *,
        retry_attempts: int = 2,
        retry_backoff_seconds: float = 0.2,
        sleep: Callable[[float], None] = time.sleep,
        metrics: MetricsRegistry = NULL_METRICS,
    ):
        self._client = client
        self._table = "patentes"
        self._retry_attempts = retry_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._sleep = sleep
        self._metrics = metrics

    def _execute_read(self, operation_name: str, operation: Callable[[], Any]) -> Any:
        """Retry bounded, idempotent reads on transient transport failures."""
        started_at = time.perf_counter()
        self._metrics.add_gauge("dependency_requests_in_flight", 1, dependency="supabase")
        try:
            for attempt in range(self._retry_attempts):
                try:
                    result = operation()
                    self._metrics.increment(
                        "dependency_requests_total",
                        dependency="supabase",
                        operation=operation_name,
                        status="ok",
                    )
                    return result
                except (TimeoutError, httpx.TimeoutException) as exc:
                    if attempt + 1 == self._retry_attempts:
                        self._metrics.increment(
                            "dependency_requests_total",
                            dependency="supabase",
                            operation=operation_name,
                            status="timeout",
                        )
                        raise ExternalServiceTimeoutError("Supabase") from exc
                except (ConnectionError, httpx.TransportError):
                    if attempt + 1 == self._retry_attempts:
                        self._metrics.increment(
                            "dependency_requests_total",
                            dependency="supabase",
                            operation=operation_name,
                            status="error",
                        )
                        raise
                self._metrics.increment(
                    "dependency_retries_total",
                    dependency="supabase",
                    operation=operation_name,
                )
                self._sleep(self._retry_backoff_seconds * (2**attempt))
            raise AssertionError("unreachable")
        finally:
            self._metrics.add_gauge(
                "dependency_requests_in_flight",
                -1,
                dependency="supabase",
            )
            self._metrics.observe(
                "dependency_request_duration_seconds",
                time.perf_counter() - started_at,
                dependency="supabase",
                operation=operation_name,
            )

    def get_all(self, page: int = 1, page_size: int = 50) -> tuple[list[dict], int]:
        offset = (page - 1) * page_size
        response = self._execute_read(
            "list",
            lambda: self._client.table(self._table)
            .select(SUMMARY_COLUMNS, count="exact")
            .order("id")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        return response.data or [], response.count or 0

    def get_by_id(self, patent_id: int) -> dict | None:
        resp = self._execute_read(
            "detail",
            lambda: self._client.table(self._table)
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
        resp = self._execute_read(
            "context",
            lambda: self._client.table(self._table)
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
        resp = self._execute_read(
            "lexical_search",
            lambda: self._client.rpc(
                "search_patentes_lexical",
                {
                    "query_text": query,
                    "requested_page": page,
                    "requested_page_size": page_size,
                },
            ).execute()
        )
        result = resp.data or {}
        return result.get("data", []), result.get("count", 0)

    def search_semantic(self, query: str, top_k: int = 20) -> list[dict]:
        """Búsqueda híbrida PostgreSQL FTS + Sentence-BERT con fusión RRF.

        Llama al RPC `search_patentes_hybrid` definido en
        `migrations/002_hybrid_search_function.sql`.
        """
        query_embedding = encode_query(query)
        resp = self._execute_read(
            "semantic_search",
            lambda: self._client.rpc(
                "search_patentes_hybrid",
                {
                    "query_text": query,
                    "query_embedding": query_embedding,
                    "top_k": top_k,
                },
            ).execute()
        )
        return resp.data or []

    def get_similares(self, patent_id: int, top_k: int = 10) -> list[dict]:
        """KNN puro sobre el embedding de la patente dada. Devuelve las
        `top_k` patentes más cercanas (excluyendo la propia)."""
        resp = self._execute_read(
            "similar_patents",
            lambda: self._client.rpc(
                "patentes_similares",
                {"patent_id": patent_id, "top_k": top_k},
            ).execute()
        )
        return resp.data or []
