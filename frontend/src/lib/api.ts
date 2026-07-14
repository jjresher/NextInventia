const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Versión resumida de una patente. Refleja las columnas devueltas por
 * `SUMMARY_COLUMNS` en el backend; incluye los campos nuevos (`apc`, `ww`,
 * `pd`, `lg_st`, `cluster_id`) y deja los legacy (`pc`, `ws`, `ls`)
 * opcionales para compatibilidad con datos viejos no migrados.
 */
export interface PatentSummary {
  id: number;
  pn: string;
  ti?: string;
  ab?: string;
  cpc?: string;
  ic?: string;
  apc?: string | null;
  pd?: string | null;
  ww?: string | null;
  lg_st?: string | null;
  cluster_id?: number | null;
  espacenet?: string;

  // Campos legacy: existen para datos viejos pero no se llenan en cargas nuevas.
  pc?: string | null;
  ws?: string | null;
  ls?: string | null;
}

export interface Patent extends PatentSummary {
  descripcion?: string;
  claimen?: string;
}

export interface PaginatedResponse {
  data: PatentSummary[];
  count: number;
  page: number;
  page_size: number;
}

export interface SemanticSearchResult extends PatentSummary {
  /** Score de Reciprocal Rank Fusion (0–~0.033). Más alto = más relevante. */
  rrf_score: number | null;
  /** Posición en el ranking BM25/FTS (null si solo apareció en semántico). */
  fts_rank: number | null;
  /** Posición en el ranking semántico/KNN (null si solo apareció en léxico). */
  sem_rank: number | null;
}

export interface SemanticSearchResponse {
  query: string;
  data: SemanticSearchResult[];
  count: number;
}

export interface SimilarPatent {
  id: number;
  pn?: string | null;
  ti?: string | null;
  ab?: string | null;
  ww?: string | null;
  apc?: string | null;
  cluster_id?: number | null;
  /** Distancia coseno (0 = idénticas, 2 = opuestas). */
  distance: number | null;
}

export interface SimilarPatentsResponse {
  patent_id: number;
  data: SimilarPatent[];
  count: number;
}

/**
 * Listado paginado clásico. Si se pasa `query`, hace búsqueda léxica con ILIKE
 * sobre `ti`, `ab`, `pn`, `ww` y `apc` (no usa embeddings).
 */
export async function fetchPatents(
  page = 1,
  pageSize = 20,
  query?: string
): Promise<PaginatedResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (query) params.set("q", query);

  const res = await fetch(`${API_URL}/patentes/?${params}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

export async function fetchPatentById(id: number): Promise<Patent> {
  const res = await fetch(`${API_URL}/patentes/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

/**
 * Búsqueda híbrida BM25 + Sentence-BERT con fusión RRF. Devuelve `top_k`
 * resultados ordenados por `rrf_score`. Funciona en lenguaje natural y en
 * español o inglés indistintamente (modelo multilingüe).
 *
 * La primera llamada paga el coste de cargar el modelo en el backend (~3 s);
 * las siguientes son ~50–150 ms.
 */
export async function searchSemantic(
  query: string,
  topK = 20
): Promise<SemanticSearchResponse> {
  const res = await fetch(`${API_URL}/patentes/search/semantic`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK }),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}

/**
 * KNN puro sobre el embedding de la patente dada. Devuelve las `topK`
 * patentes más cercanas en el espacio semántico, excluyendo la propia.
 */
export async function fetchSimilarPatents(
  id: number,
  topK = 8
): Promise<SimilarPatentsResponse> {
  const res = await fetch(
    `${API_URL}/patentes/${id}/similares?top_k=${topK}`,
    { cache: "no-store" }
  );
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return res.json();
}
