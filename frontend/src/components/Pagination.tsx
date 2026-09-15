"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { getVisiblePages } from "@/lib/pagination.mjs";

interface Props {
  currentPage: number;
  totalPages: number;
}

export default function Pagination({ currentPage, totalPages }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();

  if (totalPages <= 1) return null;

  function goToPage(page: number) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", String(page));
    router.push(`/?${params}`);
  }

  const pages = getVisiblePages(currentPage, totalPages);

  return (
    <nav
      aria-label="Paginación de resultados"
      className="flex items-center justify-center gap-1.5 mt-10"
    >
      <button
        type="button"
        aria-label="Ir a la página anterior"
        onClick={() => goToPage(currentPage - 1)}
        disabled={currentPage <= 1}
        className="flex items-center gap-1 px-3.5 py-2 rounded-xl text-sm font-medium text-gray-600 hover:bg-white hover:shadow-sm hover:text-primary-700 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200 border border-transparent hover:border-gray-200"
      >
        <ChevronLeft aria-hidden="true" className="w-4 h-4" />
        Anterior
      </button>

      <div className="flex items-center gap-1">
        {pages.map((p, i) =>
          p === "..." ? (
            <span
              key={`dots-${i}`}
              aria-hidden="true"
              className="px-2 text-gray-300 select-none"
            >
              ···
            </span>
          ) : (
            <button
              key={p}
              type="button"
              aria-label={`Ir a la página ${p}`}
              aria-current={p === currentPage ? "page" : undefined}
              onClick={() => goToPage(p)}
              className={`w-10 h-10 rounded-xl text-sm font-medium transition-all duration-200 ${
                p === currentPage
                  ? "bg-gradient-to-br from-primary-600 to-accent-600 text-white shadow-md shadow-primary-500/25"
                  : "text-gray-600 hover:bg-white hover:shadow-sm hover:text-primary-700 border border-transparent hover:border-gray-200"
              }`}
            >
              {p}
            </button>
          )
        )}
      </div>

      <button
        type="button"
        aria-label="Ir a la página siguiente"
        onClick={() => goToPage(currentPage + 1)}
        disabled={currentPage >= totalPages}
        className="flex items-center gap-1 px-3.5 py-2 rounded-xl text-sm font-medium text-gray-600 hover:bg-white hover:shadow-sm hover:text-primary-700 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200 border border-transparent hover:border-gray-200"
      >
        Siguiente
        <ChevronRight aria-hidden="true" className="w-4 h-4" />
      </button>
    </nav>
  );
}
