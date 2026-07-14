"use client";

import { useState, useRef, useEffect } from "react";
import { Sparkles, Send, ChevronDown, Bot, User } from "lucide-react";
import ReactMarkdown from "react-markdown";
import Link from "next/link";

interface Message {
  role: "user" | "model";
  content: string;
}

interface PatentContext {
  id: number;
  pn?: string;
  ti?: string;
  ab?: string;
  apc?: string | null;
  pc?: string | null;
  cpc?: string;
  pd?: string | null;
  [key: string]: unknown;
}

interface Props {
  patents: PatentContext[];
  query: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function PatentChat({ patents, query }: Props) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "model",
      content: `Hola! Encontré **${patents.length} patentes** para "${query}". ¿Qué quieres saber sobre estos resultados?`,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (open) bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  useEffect(() => {
    setMessages([
      {
        role: "model",
        content: `Hola! Encontré **${patents.length} patentes** para "${query}". ¿Qué quieres saber sobre estos resultados?`,
      },
    ]);
  }, [query, patents.length]);

  async function sendMessage() {
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: "user", content: text };
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history: messages.slice(1),
          patents_context: patents,
        }),
      });

      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      setMessages([...newHistory, { role: "model", content: data.reply }]);
    } catch (err) {
      console.error("[PatentChat] error:", err);
      setMessages([
        ...newHistory,
        { role: "model", content: "Ocurrió un error al conectar con el asistente. Intenta de nuevo." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header — siempre visible */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-between w-full px-4 py-3 bg-gradient-to-r from-primary-600 to-accent-600 text-white rounded-2xl shadow-md hover:shadow-lg transition-all duration-200"
      >
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4" />
          <span className="font-semibold text-sm">Asistente IA</span>
          <span className="px-2 py-0.5 bg-white/20 rounded-full text-xs">
            {patents.length} patentes
          </span>
        </div>
        <ChevronDown
          className={`w-4 h-4 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>

      {/* Panel de chat */}
      {open && (
        <div className="mt-2 flex flex-col bg-white/90 backdrop-blur-sm border border-gray-100 rounded-2xl shadow-lg overflow-hidden"
          style={{ height: "480px" }}
        >
          {/* Mensajes */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "model" && (
                  <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
                    <Bot className="w-3.5 h-3.5 text-white" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-gradient-to-r from-primary-600 to-accent-600 text-white rounded-br-sm"
                      : "bg-gray-100 text-gray-800 rounded-bl-sm"
                  }`}
                >
                  {msg.role === "model" ? (
                    <ReactMarkdown
                      components={{
                        p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
                        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                        ul: ({ children }) => <ul className="list-disc pl-4 space-y-0.5 mb-3">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal pl-4 space-y-0.5">{children}</ol>,
                        li: ({ children }) => <li>{children}</li>,
                        code: ({ children }) => <code className="bg-gray-200 px-1 rounded text-xs font-mono">{children}</code>,
                        a: ({ href, children }) =>
                          href?.startsWith("/patentes/") ? (
                            <Link
                              href={href}
                              className="inline-flex items-center gap-1 px-2 py-0.5 bg-primary-100 text-primary-700 rounded-md font-mono text-xs font-medium hover:bg-primary-200 transition-colors"
                            >
                              {children}
                            </Link>
                          ) : (
                            <a href={href} target="_blank" rel="noopener noreferrer" className="underline text-primary-600 hover:text-primary-800">
                              {children}
                            </a>
                          ),
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  ) : (
                    msg.content
                  )}
                </div>
                {msg.role === "user" && (
                  <div className="shrink-0 w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center">
                    <User className="w-3.5 h-3.5 text-gray-600" />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex gap-2 justify-start">
                <div className="shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
                  <Bot className="w-3.5 h-3.5 text-white" />
                </div>
                <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t border-gray-100 flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Pregunta sobre estas patentes..."
              rows={1}
              className="flex-1 resize-none rounded-xl border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-300 focus:border-transparent bg-gray-50 placeholder-gray-400"
              style={{ maxHeight: "80px" }}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              className="shrink-0 w-9 h-9 rounded-xl bg-gradient-to-r from-primary-600 to-accent-600 text-white flex items-center justify-center hover:shadow-md transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
