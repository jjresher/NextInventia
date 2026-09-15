"use client";

import { useEffect } from "react";
import {
  CHAT_CONTEXT_KEY,
  createChatContext,
  removeLegacyChatContext,
} from "@/lib/chatContext.mjs";

interface Props {
  query: string;
  patents: Array<{ id: number }>;
}

export default function SearchContextStore({ query, patents }: Props) {
  useEffect(() => {
    removeLegacyChatContext(sessionStorage);
    sessionStorage.setItem(
      CHAT_CONTEXT_KEY,
      JSON.stringify(createChatContext(query, patents))
    );
  }, [query, patents]);

  return null;
}
