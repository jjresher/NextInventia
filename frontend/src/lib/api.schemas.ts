import { z } from "zod";
import type { components } from "./api.generated";

type Schema<Name extends keyof components["schemas"]> = components["schemas"][Name];

const nullableText = z.string().nullable().optional();

export const patentSummarySchema = z.object({
  id: z.number().int(),
  pn: z.string(),
  ab: nullableText,
  apc: nullableText,
  cluster_id: z.number().int().nullable().optional(),
  cpc: nullableText,
  espacenet: nullableText,
  ic: nullableText,
  lg_st: nullableText,
  ls: nullableText,
  pc: nullableText,
  pd: nullableText,
  ti: nullableText,
  ws: nullableText,
  ww: nullableText,
}) satisfies z.ZodType<Schema<"PatentSummary">>;

export const patentSchema = patentSummarySchema.extend({
  claimen: nullableText,
  descripcion: nullableText,
}) satisfies z.ZodType<Schema<"Patent">>;

export const paginatedResponseSchema = z.object({
  count: z.number().int().nonnegative(),
  data: z.array(patentSummarySchema),
  page: z.number().int().positive(),
  page_size: z.number().int().positive(),
}) satisfies z.ZodType<Schema<"PaginatedResponse">>;

const semanticSearchResultSchema = patentSummarySchema.extend({
  fts_rank: z.number().int().nullable().optional(),
  rrf_score: z.number().nullable().optional(),
  sem_rank: z.number().int().nullable().optional(),
}) satisfies z.ZodType<Schema<"SemanticSearchResult">>;

export const semanticSearchResponseSchema = z.object({
  count: z.number().int().nonnegative(),
  data: z.array(semanticSearchResultSchema),
  query: z.string(),
}) satisfies z.ZodType<Schema<"SemanticSearchResponse">>;

const similarPatentSchema = z.object({
  id: z.number().int(),
  pn: nullableText,
  ti: nullableText,
  ab: nullableText,
  ww: nullableText,
  apc: nullableText,
  cluster_id: z.number().int().nullable().optional(),
  distance: z.number().nullable().optional(),
}) satisfies z.ZodType<Schema<"SimilarPatent">>;

export const similarPatentsResponseSchema = z.object({
  patent_id: z.number().int(),
  data: z.array(similarPatentSchema),
  count: z.number().int().nonnegative(),
}) satisfies z.ZodType<Schema<"SimilarPatentsResponse">>;

const classificationPathSchema = z.object({
  code: z.string(),
  title: z.string(),
  level: z.enum(["section", "class", "subclass", "main_group"]),
});

const recommendedCpcSchema = z.object({
  code: z.string(),
  title: z.string(),
  level: z.enum(["main_group", "subgroup"]),
  classification_path: z.array(classificationPathSchema).default([]),
  reason: z.string(),
  confidence: z.enum(["high", "medium", "low"]),
  retrieval_score: z.number(),
});

export const cpcClassificationResponseSchema = z.object({
  recommended_codes: z.array(recommendedCpcSchema),
  keywords: z.array(z.string()),
  google_patents_query: z.string(),
  notes: z.string(),
  local_fallback: z.boolean(),
}) satisfies z.ZodType<Schema<"CpcClassificationResponse">>;

export const chatResponseSchema = z.object({
  reply: z.string(),
}) satisfies z.ZodType<Schema<"ChatResponse">>;
