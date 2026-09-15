export const CHAT_CONTEXT_KEY = "patentologos.chat-context";
export const CHAT_CONTEXT_VERSION = 1;
const MAX_PATENT_IDS = 20;
const LEGACY_KEYS = ["chat_context_query", "chat_context_patents"];
const MAX_HISTORY_TURNS = 12;
const MAX_MESSAGE_CHARS = 2_000;
const MAX_HISTORY_CHARS = 10_000;

export function removeLegacyChatContext(storage) {
  for (const key of LEGACY_KEYS) storage.removeItem(key);
}

export function createChatContext(query, patents) {
  const patentIds = [
    ...new Set(
      patents
        .map((patent) => patent.id)
        .filter((id) => Number.isInteger(id) && id > 0)
    ),
  ].slice(0, MAX_PATENT_IDS);
  return {
    version: CHAT_CONTEXT_VERSION,
    query,
    patentIds,
  };
}

export function buildChatHistory(messages) {
  const selected = [];
  let usedChars = 0;
  for (const message of messages.slice(-MAX_HISTORY_TURNS).toReversed()) {
    const content = message.content.trim().slice(0, MAX_MESSAGE_CHARS);
    if (!content || usedChars + content.length > MAX_HISTORY_CHARS) continue;
    selected.push({ role: message.role, content });
    usedChars += content.length;
  }
  return selected.reverse();
}

export function readChatContext(storage, expectedQuery) {
  const raw = storage.getItem(CHAT_CONTEXT_KEY);
  if (!raw) return null;

  try {
    const value = JSON.parse(raw);
    const validIds =
      Array.isArray(value.patentIds) &&
      value.patentIds.length <= MAX_PATENT_IDS &&
      value.patentIds.every((id) => Number.isInteger(id) && id > 0) &&
      new Set(value.patentIds).size === value.patentIds.length;

    if (
      value.version !== CHAT_CONTEXT_VERSION ||
      value.query !== expectedQuery ||
      !validIds
    ) {
      storage.removeItem(CHAT_CONTEXT_KEY);
      return null;
    }
    return value;
  } catch {
    storage.removeItem(CHAT_CONTEXT_KEY);
    return null;
  }
}
