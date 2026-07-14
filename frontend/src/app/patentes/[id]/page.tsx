import Link from "next/link";
import BackButton from "@/components/BackButton";
import { fetchPatentById, fetchSimilarPatents, type SimilarPatent } from "@/lib/api";
import { notFound } from "next/navigation";
import {
  ExternalLink,
  FileText,
  Tag,
  Layers,
  ScrollText,
  BookOpen,
  Shield,
  Building2,
  Calendar,
  Sparkles,
  Network,
} from "lucide-react";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function PatentDetailPage({ params }: Props) {
  const { id } = await params;
  const patentId = Number(id);

  if (isNaN(patentId)) notFound();

  let patent;
  try {
    patent = await fetchPatentById(patentId);
  } catch {
    notFound();
  }

  // Carga "patentes similares" en paralelo. Si el embedding aún no existe
  // o el RPC falla, ignoramos y simplemente no mostramos la sección.
  let similar: SimilarPatent[] = [];
  try {
    const sim = await fetchSimilarPatents(patentId, 8);
    similar = sim.data;
  } catch {
    similar = [];
  }

  const topic = patent.ww || patent.ws || "";
  const status = patent.lg_st || patent.ls || "";

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-fade-in">
      <BackButton />

      <div className="bg-white/80 backdrop-blur-sm rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        {/* Header band */}
        <div className="bg-gradient-to-r from-primary-600 to-accent-600 px-8 py-6 text-white">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-white/20 backdrop-blur-sm rounded-lg text-sm font-mono">
              <Tag className="w-3.5 h-3.5" />
              {patent.pn}
            </span>
            {status && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-white/20 backdrop-blur-sm rounded-lg text-sm font-medium">
                <Shield className="w-3.5 h-3.5" />
                Estado: {status}
              </span>
            )}
            {topic && (
              <span className="px-3 py-1 bg-white/15 backdrop-blur-sm rounded-lg text-sm">
                {topic}
              </span>
            )}
            {patent.cluster_id != null && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-white/15 backdrop-blur-sm rounded-lg text-sm">
                <Network className="w-3.5 h-3.5" />
                Cluster #{patent.cluster_id}
              </span>
            )}
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold leading-tight">
            {patent.ti || "Sin título"}
          </h1>
          <div className="mt-4 flex flex-wrap gap-3 text-sm text-white/90">
            {patent.apc && (
              <span className="inline-flex items-center gap-1.5">
                <Building2 className="w-4 h-4" />
                {patent.apc}
              </span>
            )}
            {patent.pd && (
              <span className="inline-flex items-center gap-1.5">
                <Calendar className="w-4 h-4" />
                {patent.pd}
              </span>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="p-8 space-y-0">
          {patent.cpc && (
            <Section icon={Layers} title="Clasificación CPC">
              <div className="flex flex-wrap gap-2">
                {patent.cpc.split(";").map((code) => (
                  <span
                    key={code}
                    className="px-2.5 py-1 bg-primary-50 border border-primary-100 text-primary-700 rounded-lg text-xs font-mono"
                  >
                    {code.trim()}
                  </span>
                ))}
              </div>
            </Section>
          )}

          {patent.ic && (
            <Section icon={Layers} title="Clasificación IPC">
              <div className="flex flex-wrap gap-2">
                {patent.ic.split(";").map((code) => (
                  <span
                    key={code}
                    className="px-2.5 py-1 bg-gray-50 border border-gray-200 text-gray-600 rounded-lg text-xs font-mono"
                  >
                    {code.trim()}
                  </span>
                ))}
              </div>
            </Section>
          )}

          {patent.ab && (
            <Section icon={FileText} title="Resumen (Abstract)">
              <p className="text-gray-700 leading-relaxed whitespace-pre-line">
                {cleanHtml(patent.ab)}
              </p>
            </Section>
          )}

          {patent.descripcion && (
            <Section icon={BookOpen} title="Descripción">
              <div className="text-gray-700 leading-relaxed max-h-96 overflow-y-auto pr-2 whitespace-pre-line rounded-xl bg-gray-50/50 p-4 border border-gray-100 text-sm">
                {cleanHtml(patent.descripcion)}
              </div>
            </Section>
          )}

          {patent.claimen && (
            <Section icon={ScrollText} title="Reivindicaciones (Claims)">
              <div className="text-gray-700 leading-relaxed max-h-96 overflow-y-auto pr-2 whitespace-pre-line rounded-xl bg-gray-50/50 p-4 border border-gray-100 text-sm">
                {cleanHtml(patent.claimen)}
              </div>
            </Section>
          )}

          {patent.espacenet && (
            <Section icon={ExternalLink} title="Enlace externo">
              <a
                href={patent.espacenet}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-primary-600 to-accent-600 text-white text-sm font-medium rounded-xl hover:from-primary-700 hover:to-accent-600 shadow-md shadow-primary-500/20 hover:shadow-lg hover:shadow-primary-500/30 transition-all duration-200 active:scale-[0.98]"
              >
                <ExternalLink className="w-4 h-4" />
                Ver en Espacenet
              </a>
            </Section>
          )}
        </div>
      </div>

      {/* === Patentes similares (KNN sobre embeddings) === */}
      {similar.length > 0 && (
        <div className="space-y-4 animate-slide-up">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-800">
              <Sparkles className="w-5 h-5 text-primary-500" />
              Patentes similares
            </h2>
            <span className="text-xs text-gray-400 bg-gray-50 px-3 py-1 rounded-full">
              KNN sobre embedding · distancia coseno
            </span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {similar.map((s) => (
              <Link
                key={s.id}
                href={`/patentes/${s.id}`}
                className="group block rounded-xl bg-white/80 backdrop-blur-sm border border-gray-100 p-4 hover:shadow-lg hover:shadow-primary-500/5 hover:border-primary-200 transition-all duration-300 hover:-translate-y-0.5"
              >
                <div className="flex items-start justify-between gap-3 mb-2">
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-50 border border-gray-100 text-gray-700 rounded-md text-[11px] font-mono">
                    <Tag className="w-3 h-3" />
                    {s.pn}
                  </span>
                  {s.distance != null && (
                    <span className="text-[10px] font-mono text-primary-500">
                      d={s.distance.toFixed(3)}
                    </span>
                  )}
                </div>
                <p className="text-sm font-medium text-gray-900 group-hover:text-primary-700 transition-colors line-clamp-2">
                  {s.ti || "Sin título"}
                </p>
                <div className="flex flex-wrap items-center gap-1.5 mt-2">
                  {s.ww && (
                    <span className="px-2 py-0.5 bg-primary-50 text-primary-600 rounded-md text-[11px]">
                      {s.ww}
                    </span>
                  )}
                  {s.cluster_id != null && (
                    <span className="px-2 py-0.5 bg-amber-50 text-amber-700 rounded-md text-[11px] font-medium">
                      cluster #{s.cluster_id}
                    </span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3 py-6 border-b border-gray-100 last:border-b-0">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-500 uppercase tracking-wide">
        <Icon className="w-4 h-4 text-primary-400" />
        {title}
      </h2>
      {children}
    </div>
  );
}

function cleanHtml(text: string): string {
  return text
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}
