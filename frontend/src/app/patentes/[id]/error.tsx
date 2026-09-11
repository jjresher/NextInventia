"use client";

import Link from "next/link";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { useEffect } from "react";

export default function PatentDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("No se pudo cargar el detalle de la patente", error);
  }, [error]);

  return (
    <div className="mx-auto max-w-xl rounded-2xl border border-amber-200 bg-white/90 p-8 text-center shadow-sm">
      <AlertTriangle className="mx-auto mb-4 h-10 w-10 text-amber-500" />
      <h1 className="text-xl font-semibold text-gray-900">
        No pudimos cargar esta patente
      </h1>
      <p className="mt-2 text-sm leading-relaxed text-gray-600">
        El servicio puede estar tardando o temporalmente no disponible. Puedes
        volver a intentarlo sin perder tu navegación.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <button
          type="button"
          onClick={reset}
          className="inline-flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-primary-700"
        >
          <RefreshCw className="h-4 w-4" />
          Reintentar
        </button>
        <Link
          href="/"
          className="rounded-xl border border-gray-200 px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Volver al catálogo
        </Link>
      </div>
    </div>
  );
}
