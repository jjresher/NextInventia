import { Suspense } from "react";
import {
  fetchPatents,
  searchSemantic,
  type PatentSummary,
  type SemanticSearchResult,
} from "@/lib/api";
import PatentCard from "@/components/PatentCard";
import SearchBar from "@/components/SearchBar";
import Pagination from "@/components/Pagination";
import SearchContextStore from "@/components/SearchContextStore";
import { Database, Search, FileText, Sparkles } from "lucide-react";

interface Props {
  searchParams: Promise<{ page?: string; q?: string }>;
}

export default async function HomePage({ searchParams }: Props) {
  const params = await searchParams;
  const page = Number(params.page) || 1;
  const query = (params.q ?? "").trim() || undefined;

  // Total siempre se calcula contra el listado paginado para la barra de "X patentes indexadas".
  let total = 0;
  let listResponse: { data: PatentSummary[]; count: number; page_size: number } | null = null;
  let semanticResults: SemanticSearchResult[] | null = null;
  let error: string | null = null;

  try {
    if (query) {
      // Con query → búsqueda híbrida BM25 + Sentence-BERT con RRF.
      const sem = await searchSemantic(query, 20);
      semanticResults = sem.data;
      total = sem.count;
      const totalsResp = await fetchPatents(1, 1);
      listResponse = { data: [], count: totalsResp.count, page_size: 20 };
    } else {
      // Sin query → listado paginado normal.
      const r = await fetchPatents(page, 20);
      listResponse = { data: r.data, count: r.count, page_size: r.page_size };
      total = r.count;
    }
  } catch (e) {
    error = e instanceof Error ? e.message : "Error desconocido";
  }

  const totalPages =
    !query && listResponse
      ? Math.ceil(listResponse.count / listResponse.page_size)
      : 0;

  return (
    <div className="space-y-10">
      {/* Hero */}
      <section className="relative text-center space-y-6 py-10 animate-fade-in">
        <div className="absolute inset-0 -z-10 overflow-hidden">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-gradient-to-r from-primary-200/30 via-accent-400/20 to-primary-200/30 rounded-full blur-3xl" />
        </div>

        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-primary-50 border border-primary-100 text-primary-700 text-sm font-medium">
          <Database className="w-3.5 h-3.5" />
          {listResponse?.count ?? 0} patentes indexadas
        </div>

        <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
          <span className="gradient-text">Buscador de Patentes</span>
        </h1>
        <p className="text-gray-500 max-w-xl mx-auto text-lg leading-relaxed">
          Búsqueda híbrida con BM25 y embeddings semánticos multilingües.
        </p>

        <div className="flex justify-center pt-2">
          <Suspense>
            <SearchBar key={query ?? ""} />
          </Suspense>
        </div>
      </section>

      {error && (
        <div className="flex items-center gap-3 bg-red-50 border border-red-200 text-red-700 rounded-2xl p-5 animate-fade-in">
          <div className="shrink-0 w-10 h-10 rounded-xl bg-red-100 flex items-center justify-center">
            <span className="text-lg">!</span>
          </div>
          <div>
            <p className="font-medium">Error de conexión</p>
            <p className="text-sm text-red-600/80">{error}</p>
          </div>
        </div>
      )}

      {/* === Modo búsqueda híbrida === */}
      {!error && query && semanticResults && (
        <SearchContextStore query={query} patents={semanticResults} />
      )}
      {!error && query && semanticResults && (
        <div
          className="animate-slide-up"
          style={{ animationDelay: "0.15s", animationFillMode: "backwards" }}
        >
          <div className="flex items-center justify-between px-1 flex-wrap gap-3 mb-6">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Sparkles className="w-4 h-4 text-primary-500" />
              <span>
                Top{" "}
                <span className="font-semibold text-gray-700">
                  {semanticResults.length}
                </span>{" "}
                resultados híbridos para{" "}
                <span className="font-medium text-primary-600">
                  &quot;{query}&quot;
                </span>
              </span>
            </div>
            <span className="text-xs text-gray-400 bg-gray-50 px-3 py-1 rounded-full">
              ranking · BM25 + Sentence-BERT (RRF)
            </span>
          </div>

          <div className="grid gap-4">
            {semanticResults.map((p, idx) => (
              <div
                key={p.id}
                className="animate-slide-up"
                style={{ animationDelay: `${0.05 * idx}s`, animationFillMode: "backwards" }}
              >
                <PatentCard
                  patent={p}
                  ftsRank={p.fts_rank}
                  semRank={p.sem_rank}
                  rrfScore={p.rrf_score}
                />
              </div>
            ))}
            {semanticResults.length === 0 && <EmptyState />}
          </div>
        </div>
      )}

      {/* === Modo listado paginado === */}
      {!error && !query && listResponse && (
        <div
          className="space-y-6 animate-slide-up"
          style={{ animationDelay: "0.15s", animationFillMode: "backwards" }}
        >
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <FileText className="w-4 h-4" />
              <span>
                <span className="font-semibold text-gray-700">{total}</span>{" "}
                patente{total !== 1 && "s"} en el corpus
              </span>
            </div>
            <span className="text-xs text-gray-400 bg-gray-50 px-3 py-1 rounded-full">
              Página {page} de {totalPages}
            </span>
          </div>

          <div className="grid gap-4">
            {listResponse.data.map((patent, idx) => (
              <div
                key={patent.id}
                className="animate-slide-up"
                style={{ animationDelay: `${0.05 * idx}s`, animationFillMode: "backwards" }}
              >
                <PatentCard patent={patent} />
              </div>
            ))}
          </div>

          {listResponse.data.length === 0 && <EmptyState />}

          <Suspense>
            <Pagination currentPage={page} totalPages={totalPages} />
          </Suspense>
        </div>
      )}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="text-center py-20 space-y-4">
      <div className="w-16 h-16 mx-auto rounded-2xl bg-gray-100 flex items-center justify-center">
        <Search className="w-7 h-7 text-gray-400" />
      </div>
      <p className="text-gray-500 text-lg">No se encontraron patentes.</p>
      <p className="text-gray-400 text-sm">Intenta con otros términos de búsqueda.</p>
    </div>
  );
}
