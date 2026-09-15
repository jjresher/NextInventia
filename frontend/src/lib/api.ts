import { z } from "zod";
import type { components } from "./api.generated";
import {
  chatResponseSchema,
  cpcClassificationResponseSchema,
  paginatedResponseSchema,
  patentSchema,
  semanticSearchResponseSchema,
  similarPatentsResponseSchema,
} from "./api.schemas";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const CATALOG_REVALIDATE_SECONDS = 60;
const PATENT_REVALIDATE_SECONDS = 300;
const API_TIMEOUT_MS = positiveMilliseconds(
  process.env.NEXT_PUBLIC_API_TIMEOUT_MS,
  15_000
);
const LONG_API_TIMEOUT_MS = positiveMilliseconds(
  process.env.NEXT_PUBLIC_LONG_API_TIMEOUT_MS,
  60_000
);

interface RequestOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
}

export class ApiResponseError extends Error {
  constructor(public readonly status: number) {
    super(`Error ${status}`);
    this.name = "ApiResponseError";
  }
}

export class ApiContractError extends Error {
  constructor() {
    super("La API devolvió una respuesta incompatible.");
    this.name = "ApiContractError";
  }
}

export class ApiTimeoutError extends Error {
  constructor() {
    super("La solicitud tardó demasiado. Intenta nuevamente.");
    this.name = "ApiTimeoutError";
  }
}

export class ApiCancelledError extends Error {
  constructor() {
    super("La solicitud fue cancelada.");
    this.name = "ApiCancelledError";
  }
}

function positiveMilliseconds(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

async function apiFetch(
  input: string,
  init: RequestInit,
  options: RequestOptions,
  defaultTimeoutMs: number
): Promise<Response> {
  const timeoutSignal = AbortSignal.timeout(options.timeoutMs ?? defaultTimeoutMs);
  const signal = options.signal
    ? AbortSignal.any([options.signal, timeoutSignal])
    : timeoutSignal;
  try {
    return await fetch(input, { ...init, signal });
  } catch (error) {
    if (timeoutSignal.aborted) throw new ApiTimeoutError();
    if (options.signal?.aborted) throw new ApiCancelledError();
    throw error;
  }
}

type Schema<Name extends keyof components["schemas"]> = components["schemas"][Name];

export type PatentSummary = Schema<"PatentSummary">;
export type Patent = Schema<"Patent">;
export type PaginatedResponse = Schema<"PaginatedResponse">;
export type SemanticSearchResult = Schema<"SemanticSearchResult">;
export type SemanticSearchResponse = Schema<"SemanticSearchResponse">;
export type SimilarPatent = Schema<"SimilarPatent">;
export type SimilarPatentsResponse = Schema<"SimilarPatentsResponse">;
export type CpcClassificationResponse = z.output<typeof cpcClassificationResponseSchema>;
export type ChatMessage = Schema<"Message">;

async function parseResponse<T>(response: Response, schema: z.ZodType<T>): Promise<T> {
  const payload: unknown = await response.json().catch(() => {
    throw new ApiContractError();
  });
  const parsed = schema.safeParse(payload);
  if (!parsed.success) throw new ApiContractError();
  return parsed.data;
}

/**
 * Listado paginado clásico. Si se pasa `query`, hace búsqueda léxica con ILIKE
 * sobre `ti`, `ab`, `pn`, `ww` y `apc` (no usa embeddings).
 */
export async function fetchPatents(
  page = 1,
  pageSize = 20,
  query?: string,
  options: RequestOptions = {}
): Promise<PaginatedResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (query) params.set("q", query);

  const res = await apiFetch(
    `${API_URL}/patentes/?${params}`,
    { next: { revalidate: CATALOG_REVALIDATE_SECONDS } },
    options,
    API_TIMEOUT_MS
  );
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return parseResponse(res, paginatedResponseSchema);
}

export async function fetchPatentById(
  id: number,
  options: RequestOptions = {}
): Promise<Patent> {
  const res = await apiFetch(
    `${API_URL}/patentes/${id}`,
    { next: { revalidate: PATENT_REVALIDATE_SECONDS } },
    options,
    API_TIMEOUT_MS
  );
  if (!res.ok) throw new ApiResponseError(res.status);
  return parseResponse(res, patentSchema);
}

/**
 * Búsqueda híbrida PostgreSQL FTS + Sentence-BERT con fusión RRF. Devuelve `top_k`
 * resultados ordenados por `rrf_score`. Funciona en lenguaje natural y en
 * español o inglés indistintamente (modelo multilingüe).
 *
 * La primera llamada paga el coste de cargar el modelo en el backend (~3 s);
 * las siguientes son ~50–150 ms.
 */
export async function searchSemantic(
  query: string,
  topK = 20,
  options: RequestOptions = {}
): Promise<SemanticSearchResponse> {
  const res = await apiFetch(
    `${API_URL}/patentes/search/semantic`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, top_k: topK }),
      cache: "no-store",
    },
    options,
    LONG_API_TIMEOUT_MS
  );
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return parseResponse(res, semanticSearchResponseSchema);
}

/**
 * KNN puro sobre el embedding de la patente dada. Devuelve las `topK`
 * patentes más cercanas en el espacio semántico, excluyendo la propia.
 */
export async function fetchSimilarPatents(
  id: number,
  topK = 8,
  options: RequestOptions = {}
): Promise<SimilarPatentsResponse> {
  const res = await apiFetch(
    `${API_URL}/patentes/${id}/similares?top_k=${topK}`,
    { next: { revalidate: PATENT_REVALIDATE_SECONDS } },
    options,
    LONG_API_TIMEOUT_MS
  );
  if (!res.ok) throw new Error(`Error ${res.status}`);
  return parseResponse(res, similarPatentsResponseSchema);
}

export async function recommendCpcCodes(
  description: string,
  topK = 8,
  options: RequestOptions = {}
): Promise<CpcClassificationResponse> {
  const res = await apiFetch(
    `${API_URL}/clasificacion/cpc/recommend`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description, top_k: topK }),
      cache: "no-store",
    },
    options,
    LONG_API_TIMEOUT_MS
  );

  if (!res.ok) {
    const payload = await res.json().catch(() => null);
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : "No fue posible analizar la descripción.";
    throw new Error(detail);
  }
  return parseResponse(res, cpcClassificationResponseSchema);
}

export async function sendChat(
  message: string,
  history: ChatMessage[],
  patentIds: number[],
  options: RequestOptions = {}
): Promise<string> {
  const res = await apiFetch(
    `${API_URL}/chat/`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history, patent_ids: patentIds }),
    },
    options,
    LONG_API_TIMEOUT_MS
  );
  if (!res.ok) {
    const payload: unknown = await res.json().catch(() => null);
    const detail =
      payload && typeof payload === "object" && "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : `Error ${res.status}`;
    throw new Error(detail);
  }
  const data = await parseResponse(res, chatResponseSchema);
  return data.reply;
}
