from pydantic import BaseModel, ConfigDict, Field


class _PatentBase(BaseModel):
    """Campos comunes compartidos entre la versión completa y la resumida.

    `model_config` con `extra='ignore'` evita explotar si Supabase devuelve
    columnas extra (legacy o nuevas) que aún no estén en el modelo.
    """

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    pn: str | None = None
    apc: str | None = None  # applicant company
    cpc: str | None = None
    ic: str | None = None
    ww: str | None = None  # categoría temática granular
    pd: str | None = None  # publication date (YYYY-MM-DD u otro formato libre)
    lg_st: str | None = None  # legal status
    ti: str | None = None
    ab: str | None = None
    espacenet: str | None = None

    # Campos legacy (siguen en BD por compat; nuevos imports los dejan NULL).
    pc: str | None = None
    ws: str | None = None
    ls: str | None = None


class Patent(_PatentBase):
    """Versión completa: incluye descripción y claims (texto largo)."""

    descripcion: str | None = None
    claimen: str | None = None
    cluster_id: int | None = None


class PatentSummary(_PatentBase):
    """Versión ligera para listados (sin texto largo)."""

    cluster_id: int | None = None


class PaginatedResponse(BaseModel):
    data: list[PatentSummary]
    count: int
    page: int
    page_size: int


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(20, ge=1, le=100)


class SemanticSearchResult(PatentSummary):
    """Resultado del RPC `search_patentes_hybrid`."""

    rrf_score: float | None = None
    fts_rank: int | None = None
    sem_rank: int | None = None


class SemanticSearchResponse(BaseModel):
    query: str
    data: list[SemanticSearchResult]
    count: int


class SimilarPatent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    pn: str | None = None
    ti: str | None = None
    ab: str | None = None
    ww: str | None = None
    apc: str | None = None
    cluster_id: int | None = None
    distance: float | None = None


class SimilarPatentsResponse(BaseModel):
    patent_id: int
    data: list[SimilarPatent]
    count: int
