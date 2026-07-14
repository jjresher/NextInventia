"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";

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

  const pages: (number | "...")[] = [];
  for (let i = 1; i <= totalPages; i++) {
    if (
      i === 1 ||
      i === totalPages ||
      (i >= currentPage - 2 && i <= currentPage + 2)
    ) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== "...") {
      pages.push("...");
    }
  }

  return (
    <div className="flex items-center justify-center gap-1.5 mt-10">
      <button
        onClick={() => goToPage(currentPage - 1)}
        disabled={currentPage <= 1}
        className="flex items-center gap-1 px-3.5 py-2 rounded-xl text-sm font-medium text-gray-600 hover:bg-white hover:shadow-sm hover:text-primary-700 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200 border border-transparent hover:border-gray-200"
      >
        <ChevronLeft className="w-4 h-4" />
        Anterior
      </button>

      <div className="flex items-center gap-1">
        {pages.map((p, i) =>
          p === "..." ? (
            <span key={`dots-${i}`} className="px-2 text-gray-300 select-none">
              ···
            </span>
          ) : (
            <button
              key={p}
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
        onClick={() => goToPage(currentPage + 1)}
        disabled={currentPage >= totalPages}
        className="flex items-center gap-1 px-3.5 py-2 rounded-xl text-sm font-medium text-gray-600 hover:bg-white hover:shadow-sm hover:text-primary-700 disabled:opacity-30 disabled:cursor-not-allowed transition-all duration-200 border border-transparent hover:border-gray-200"
      >
        Siguiente
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
}
