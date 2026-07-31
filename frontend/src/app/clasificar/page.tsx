import type { Metadata } from "next";
import { Database, ShieldCheck } from "lucide-react";

import CpcClassifier from "@/components/CpcClassifier";

export const metadata: Metadata = {
  title: "Clasificar CPC | Patentologos",
  description:
    "Recomienda códigos CPC y crea una ecuación de búsqueda para Google Patents.",
};

export default function ClassifyPage() {
  return (
    <div className="pb-8">
      <header className="mb-7 border-b border-slate-200 pb-6">
        <div className="flex flex-col justify-between gap-5 md:flex-row md:items-end">
          <div className="max-w-2xl">
            <p className="mb-2 text-xs font-bold uppercase tracking-[0.18em] text-indigo-700">
              Clasificación asistida
            </p>
            <h1 className="text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
              Recomendador de códigos CPC
            </h1>
            <p className="mt-3 text-base leading-7 text-slate-600">
              Compara una descripción técnica con el índice local y prepara una
              búsqueda lista para verificar en Google Patents.
            </p>
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs font-medium text-slate-600">
            <span className="flex items-center gap-2">
              <Database className="h-4 w-4 text-emerald-600" />
              Corpus local F02D
            </span>
            <span className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              Códigos validados
            </span>
          </div>
        </div>
      </header>

      <CpcClassifier />
    </div>
  );
}
