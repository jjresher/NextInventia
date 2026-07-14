import Link from "next/link";
import { FileText, ArrowRight, Tag, Building2, Calendar, Sparkles } from "lucide-react";
import type { PatentSummary } from "@/lib/api";

interface Props {
  patent: PatentSummary;
  /** Posición en el ranking BM25/FTS (sólo si viene de búsqueda híbrida). */
  ftsRank?: number | null;
  /** Posición en el ranking semántico (sólo si viene de búsqueda híbrida). */
  semRank?: number | null;
  /** Score RRF combinado (sólo si viene de búsqueda híbrida). */
  rrfScore?: number | null;
}

/**
 * Mapeo de letra de estado legal a etiqueta human-readable. Funciona tanto
 * con la columna nueva (`lg_st`) como con la legacy (`ls`).
 */
const STATUS_MAP: Record<string, { label: string; bg: string; text: string; dot: string }> = {
  G: { label: "Concedida", bg: "bg-emerald-50", text: "text-emerald-700", dot: "bg-emerald-500" },
  A: { label: "Solicitud", bg: "bg-amber-50", text: "text-amber-700", dot: "bg-amber-500" },
  B: { label: "Publicada", bg: "bg-blue-50", text: "text-blue-700", dot: "bg-blue-500" },
  F: { label: "Caducada", bg: "bg-gray-50", text: "text-gray-600", dot: "bg-gray-400" },
  U: { label: "Pendiente", bg: "bg-slate-50", text: "text-slate-600", dot: "bg-slate-400" },
};

function cleanText(s: string | null | undefined, max = 220): string {
  if (!s) return "";
  const t = s.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
  return t.length > max ? `${t.slice(0, max)}…` : t;
}

export default function PatentCard({ patent, ftsRank, semRank, rrfScore }: Props) {
  const statusKey = (patent.lg_st ?? patent.ls ?? "").toUpperCase();
  const status = STATUS_MAP[statusKey] ?? {
    label: statusKey || "—",
    bg: "bg-gray-50",
    text: "text-gray-600",
    dot: "bg-gray-400",
  };

  // Categoría temática: preferir `ww` (granular nuevo) sobre `ws` (legacy).
  const topic = patent.ww || patent.ws || "";

  // Limpiar abstract (a veces trae HTML).
  const abstract = cleanText(patent.ab, 220);

  // Determinar tipo de match (sólo aplica cuando viene de búsqueda híbrida).
  const isHybridResult = rrfScore != null;
  const matchedBoth = ftsRank != null && semRank != null;
  const matchedLexicalOnly = ftsRank != null && semRank == null;
  const matchedSemanticOnly = ftsRank == null && semRank != null;

  return (
    <Link
      href={`/patentes/${patent.id}`}
      className="group block rounded-2xl bg-white/80 backdrop-blur-sm border border-gray-100 p-6 hover:shadow-xl hover:shadow-primary-500/5 hover:border-primary-200 transition-all duration-300 hover:-translate-y-0.5"
    >
      <div className="flex items-start gap-4">
        <div className="hidden sm:flex shrink-0 w-11 h-11 rounded-xl bg-gradient-to-br from-primary-50 to-primary-100 items-center justify-center text-primary-500 group-hover:from-primary-100 group-hover:to-primary-200 transition-colors">
          <FileText className="w-5 h-5" />
        </div>

        <div className="flex-1 min-w-0 space-y-3">
          <div className="flex items-start justify-between gap-3">
            <h2 className="text-base font-semibold text-gray-900 group-hover:text-primary-700 transition-colors leading-snug line-clamp-2">
              {patent.ti || "Sin título"}
            </h2>
            {statusKey && (
              <span
                className={`shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${status.bg} ${status.text}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />
                {status.label}
              </span>
            )}
          </div>

          {/* Identificadores y contexto */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-gray-50 border border-gray-100 text-gray-700 rounded-lg text-xs font-mono">
              <Tag className="w-3 h-3" />
              {patent.pn}
            </span>
            {topic && (
              <span className="px-2.5 py-1 bg-primary-50 text-primary-600 rounded-lg text-xs font-medium">
                {topic}
              </span>
            )}
            {patent.apc && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-violet-50 text-violet-700 rounded-lg text-xs font-medium">
                <Building2 className="w-3 h-3" />
                {patent.apc.split(";")[0].trim()}
              </span>
            )}
            {patent.pd && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-gray-50 text-gray-600 rounded-lg text-xs font-mono">
                <Calendar className="w-3 h-3" />
                {patent.pd}
              </span>
            )}
            {patent.cluster_id != null && (
              <span className="px-2.5 py-1 bg-amber-50 text-amber-700 rounded-lg text-[11px] font-medium">
                cluster #{patent.cluster_id}
              </span>
            )}
          </div>

          {/* Badges del match (solo en búsqueda híbrida) */}
          {isHybridResult && (
            <div className="flex flex-wrap items-center gap-2">
              {matchedBoth && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 text-emerald-700 rounded-md text-[11px] font-medium border border-emerald-100">
                  <Sparkles className="w-3 h-3" />
                  léxico + semántico
                </span>
              )}
              {matchedLexicalOnly && (
                <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded-md text-[11px] font-medium border border-blue-100">
                  match léxico
                </span>
              )}
              {matchedSemanticOnly && (
                <span className="px-2 py-0.5 bg-fuchsia-50 text-fuchsia-700 rounded-md text-[11px] font-medium border border-fuchsia-100">
                  match semántico
                </span>
              )}
              {ftsRank != null && (
                <span className="text-[10px] font-mono text-gray-400">
                  fts #{ftsRank}
                </span>
              )}
              {semRank != null && (
                <span className="text-[10px] font-mono text-gray-400">
                  sem #{semRank}
                </span>
              )}
              {rrfScore != null && (
                <span className="ml-auto text-[10px] font-mono text-primary-500">
                  RRF {rrfScore.toFixed(4)}
                </span>
              )}
            </div>
          )}

          {abstract && (
            <p className="text-sm text-gray-500 leading-relaxed line-clamp-2">
              {abstract}
            </p>
          )}

          {patent.cpc && (
            <div className="flex flex-wrap gap-1.5">
              {patent.cpc
                .split(";")
                .slice(0, 3)
                .map((code) => (
                  <span
                    key={code}
                    className="px-2 py-0.5 bg-primary-50/60 text-primary-600/80 rounded-md text-[11px] font-mono"
                  >
                    {code.trim()}
                  </span>
                ))}
              {patent.cpc.split(";").length > 3 && (
                <span className="px-2 py-0.5 text-gray-400 text-[11px]">
                  +{patent.cpc.split(";").length - 3} más
                </span>
              )}
            </div>
          )}

          <div className="flex items-center gap-1 text-xs font-medium text-primary-500 opacity-0 group-hover:opacity-100 transition-opacity pt-1">
            Ver detalle
            <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
          </div>
        </div>
      </div>
    </Link>
  );
}
