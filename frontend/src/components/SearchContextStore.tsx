"use client";

import { useEffect } from "react";

interface Props {
  query: string;
  patents: object[];
}

export default function SearchContextStore({ query, patents }: Props) {
  useEffect(() => {
    sessionStorage.setItem("chat_context_query", query);
    sessionStorage.setItem("chat_context_patents", JSON.stringify(patents));
  }, [query, patents]);

  return null;
}
