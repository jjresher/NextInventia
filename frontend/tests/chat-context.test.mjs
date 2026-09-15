import assert from "node:assert/strict";
import test from "node:test";

import {
  CHAT_CONTEXT_KEY,
  buildChatHistory,
  createChatContext,
  readChatContext,
  removeLegacyChatContext,
} from "../src/lib/chatContext.mjs";

function memoryStorage(initialValue) {
  const values = new Map();
  if (initialValue !== undefined) {
    values.set(CHAT_CONTEXT_KEY, initialValue);
  }
  return {
    getItem: (key) => values.get(key) ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, value),
  };
}

test("serializa solo version, query e IDs", () => {
  const context = createChatContext("motor", [
    { id: 7, ab: "contenido sensible" },
    { id: 9, claimen: "reivindicacion" },
  ]);

  assert.deepEqual(context, {
    version: 1,
    query: "motor",
    patentIds: [7, 9],
  });
  assert.equal(JSON.stringify(context).includes("contenido sensible"), false);
});

test("elimina las claves antiguas que contenían patentes completas", () => {
  const storage = memoryStorage();
  storage.setItem("chat_context_query", "motor");
  storage.setItem("chat_context_patents", '[{"ab":"sensible"}]');

  removeLegacyChatContext(storage);

  assert.equal(storage.getItem("chat_context_query"), null);
  assert.equal(storage.getItem("chat_context_patents"), null);
});

test("descarta y elimina JSON corrupto", () => {
  const storage = memoryStorage("{no-json");

  assert.equal(readChatContext(storage, "motor"), null);
  assert.equal(storage.getItem(CHAT_CONTEXT_KEY), null);
});

test("descarta versiones, queries e IDs invalidos", () => {
  for (const value of [
    { version: 0, query: "motor", patentIds: [1] },
    { version: 1, query: "otra", patentIds: [1] },
    { version: 1, query: "motor", patentIds: [1, 1] },
    { version: 1, query: "motor", patentIds: [-1] },
  ]) {
    const storage = memoryStorage(JSON.stringify(value));
    assert.equal(readChatContext(storage, "motor"), null);
  }
});

test("acota el historial por turnos y presupuesto", () => {
  const messages = Array.from({ length: 14 }, (_, index) => ({
    role: index % 2 === 0 ? "user" : "model",
    content: ` ${String(index).padStart(2, "0")}${"x".repeat(998)} `,
  }));

  const history = buildChatHistory(messages);

  assert.equal(history.length, 10);
  assert.equal(
    history.reduce((total, item) => total + item.content.length, 0),
    10_000
  );
  assert.equal(history[0].content.startsWith("04"), true);
});
