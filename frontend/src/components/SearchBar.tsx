"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Search, X } from "lucide-react";

export default function SearchBar() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [focused, setFocused] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    params.set("page", "1");
    router.push(`/?${params}`);
  }

  function handleClear() {
    setQuery("");
    router.push("/?page=1");
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl" id="buscar">
      <div
        className={`flex items-center gap-3 px-5 py-3.5 rounded-2xl border transition-all duration-300 bg-white/80 backdrop-blur-sm ${
          focused
            ? "border-primary-400 shadow-lg shadow-primary-500/10 ring-4 ring-primary-100"
            : "border-gray-200 shadow-sm hover:border-primary-300 hover:shadow-md"
        }`}
      >
        <Search className={`w-5 h-5 shrink-0 transition-colors ${focused ? "text-primary-500" : "text-gray-400"}`} />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder='Lenguaje natural: "turbinas con protección contra rayos", "Sanofi", "lithium battery"...'
          className="flex-1 bg-transparent text-gray-900 placeholder-gray-400 focus:outline-none text-sm"
        />
        {query && (
          <button
            type="button"
            onClick={handleClear}
            className="p-1 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition"
          >
            <X className="w-4 h-4" />
          </button>
        )}
        <button
          type="submit"
          className="px-5 py-2 bg-gradient-to-r from-primary-600 to-accent-600 text-white text-sm font-medium rounded-xl hover:from-primary-700 hover:to-accent-600 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 transition-all duration-200 shadow-md shadow-primary-500/20 hover:shadow-lg hover:shadow-primary-500/30 active:scale-[0.98]"
        >
          Buscar
        </button>
      </div>
    </form>
  );
}
