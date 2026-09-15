"use client";

import { FormEvent, useState } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  Check,
  Clipboard,
  LoaderCircle,
  SearchCode,
  Sparkles,
} from "lucide-react";

import {
  CpcClassificationResponse,
  recommendCpcCodes,
} from "@/lib/api";

const CONFIDENCE_LABEL = {
  high: "Alta",
  medium: "Media",
  low: "Baja",
} as const;

const CONFIDENCE_STYLE = {
  high: "bg-emerald-50 text-emerald-700 border-emerald-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  low: "bg-slate-100 text-slate-600 border-slate-200",
} as const;

const EXAMPLE =
  "Sistema de control electrónico para un motor de combustión que ajusta la inyección de combustible según sensores de temperatura y velocidad.";

export default function CpcClassifier() {
  const [description, setDescription] = useState("");
  const [result, setResult] = useState<CpcClassificationResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const cleanDescription = description.trim();
    if (!cleanDescription || loading) return;

    setLoading(true);
    setError("");
    setCopied(false);
    try {
      setResult(await recommendCpcCodes(cleanDescription));
    } catch (requestError) {
      setResult(null);
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Ocurrió un error durante el análisis."
      );
    } finally {
      setLoading(false);
    }
  };

  const copyQuery = async () => {
    if (!result?.google_patents_query) return;
    await navigator.clipboard.writeText(result.google_patents_query);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };

  const googlePatentsUrl = result?.google_patents_query
    ? `https://patents.google.com/?q=${encodeURIComponent(
        result.google_patents_query
      )}`
    : "";

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)] lg:items-start">
      <form
        onSubmit={submit}
        className="border border-slate-200 bg-white shadow-sm"
      >
        <div className="border-b border-slate-200 px-5 py-4 sm:px-6">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-700">
              <SearchCode className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-base font-semibold text-slate-900">
                Descripción técnica
              </h2>
              <p className="text-sm text-slate-500">
                Describe la función, componentes y variables de control.
              </p>
            </div>
          </div>
        </div>

        <div className="space-y-4 p-5 sm:p-6">
          <label htmlFor="invention-description" className="sr-only">
            Descripción de la invención
          </label>
          <textarea
            id="invention-description"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Ejemplo: sistema electrónico que regula la inyección de combustible según temperatura, velocidad y carga del motor..."
            maxLength={6000}
            rows={12}
            className="min-h-72 w-full resize-y rounded-md border border-slate-300 bg-slate-50/60 px-4 py-3 text-[15px] leading-6 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:ring-3 focus:ring-indigo-100"
          />

          <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
            <button
              type="button"
              onClick={() => setDescription(EXAMPLE)}
              className="font-medium text-indigo-700 hover:text-indigo-900"
            >
              Usar ejemplo
            </button>
            <span>{description.length} / 6000</span>
          </div>

          {error ? (
            <div
              role="alert"
              className="flex gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          ) : null}

          <button
            type="submit"
            disabled={!description.trim() || loading}
            className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-3 focus:ring-indigo-200 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {loading ? (
              <>
                <LoaderCircle className="h-4 w-4 animate-spin" />
                Recuperando candidatos
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Analizar clasificación CPC
              </>
            )}
          </button>
        </div>
      </form>

      <section
        aria-live="polite"
        className="min-h-[32rem] border border-slate-200 bg-white shadow-sm"
      >
        {!result && !loading ? (
          <div className="flex min-h-[32rem] flex-col items-center justify-center px-8 text-center">
            <span className="mb-5 flex h-14 w-14 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-slate-500">
              <SearchCode className="h-6 w-6" />
            </span>
            <h2 className="text-base font-semibold text-slate-900">
              Aún no hay un análisis
            </h2>
            <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">
              Los códigos recuperados, sus razones y la ecuación de búsqueda
              aparecerán aquí.
            </p>
          </div>
        ) : null}

        {loading ? (
          <div className="flex min-h-[32rem] flex-col items-center justify-center px-8 text-center">
            <LoaderCircle className="h-7 w-7 animate-spin text-indigo-600" />
            <p className="mt-4 text-sm font-medium text-slate-700">
              Comparando la descripción con el corpus CPC local...
            </p>
            <p className="mt-1 text-xs text-slate-500">
              La primera consulta puede tardar mientras se carga el modelo.
            </p>
          </div>
        ) : null}

        {result ? (
          <div className="animate-fade-in">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4 sm:px-6">
              <div>
                <h2 className="text-base font-semibold text-slate-900">
                  Códigos candidatos
                </h2>
                <p className="text-sm text-slate-500">
                  Ordenados por relevancia semántica.
                </p>
              </div>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
                {result.recommended_codes.length}
              </span>
            </div>

            <div className="divide-y divide-slate-100">
              {result.recommended_codes.map((item) => (
                <article key={item.code} className="px-5 py-5 sm:px-6">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <code className="text-sm font-bold text-indigo-700">
                        {item.code}
                      </code>
                      <h3 className="mt-1 text-sm font-semibold text-slate-900">
                        {item.title}
                      </h3>
                      {item.classification_path.length > 0 ? (
                        <div
                          className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500"
                          aria-label="Ruta de clasificación"
                        >
                          {item.classification_path.map((path, pathIndex) => (
                            <span key={path.code} className="flex items-center gap-1.5">
                              {pathIndex > 0 ? (
                                <span aria-hidden="true" className="text-slate-300">
                                  /
                                </span>
                              ) : null}
                              <span title={path.title} className="font-mono">
                                {path.code}
                              </span>
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${CONFIDENCE_STYLE[item.confidence]}`}
                      >
                        {CONFIDENCE_LABEL[item.confidence]}
                      </span>
                      <span
                        title="Similitud coseno de la recuperación local"
                        className="font-mono text-xs text-slate-500"
                      >
                        {item.retrieval_score.toFixed(3)}
                      </span>
                    </div>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-600">
                    {item.reason}
                  </p>
                </article>
              ))}
            </div>

            <div className="border-t border-slate-200 bg-slate-50 px-5 py-5 sm:px-6">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Palabras clave
              </h3>
              <div className="mt-3 flex flex-wrap gap-2">
                {result.keywords.map((keyword) => (
                  <span
                    key={keyword}
                    className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700"
                  >
                    {keyword}
                  </span>
                ))}
              </div>

              <div className="mt-5">
                <div className="mb-2 flex items-center justify-between gap-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Ecuación Google Patents
                  </h3>
                  <button
                    type="button"
                    onClick={copyQuery}
                    title="Copiar ecuación"
                    className="flex h-8 items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-700 transition hover:border-indigo-300 hover:text-indigo-700"
                  >
                    {copied ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : (
                      <Clipboard className="h-3.5 w-3.5" />
                    )}
                    {copied ? "Copiada" : "Copiar"}
                  </button>
                </div>
                <div className="overflow-x-auto rounded-md border border-slate-200 bg-white p-3">
                  <code className="whitespace-pre-wrap break-words text-xs leading-5 text-slate-700">
                    {result.google_patents_query || "Sin ecuación disponible"}
                  </code>
                </div>
                {googlePatentsUrl ? (
                  <a
                    href={googlePatentsUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-3 flex h-10 w-full items-center justify-center gap-2 rounded-md border border-indigo-200 bg-indigo-50 text-sm font-semibold text-indigo-700 transition hover:bg-indigo-100"
                  >
                    Abrir en Google Patents
                    <ArrowUpRight className="h-4 w-4" />
                  </a>
                ) : null}
              </div>

              <p className="mt-4 text-xs leading-5 text-slate-500">
                {result.notes}
              </p>
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
