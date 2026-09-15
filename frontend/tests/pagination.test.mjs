import assert from "node:assert/strict";
import test from "node:test";

import { getVisiblePages } from "../src/lib/pagination.mjs";

test("no muestra controles para una sola pagina", () => {
  assert.deepEqual(getVisiblePages(1, 1), [1]);
});

test("muestra todas las paginas cuando el total es pequeno", () => {
  assert.deepEqual(getVisiblePages(3, 5), [1, 2, 3, 4, 5]);
});

test("calcula una ventana constante alrededor de la pagina actual", () => {
  assert.deepEqual(getVisiblePages(500_000, 1_000_000), [
    1,
    "...",
    499_998,
    499_999,
    500_000,
    500_001,
    500_002,
    "...",
    1_000_000,
  ]);
});

test("ajusta la ventana en los extremos", () => {
  assert.deepEqual(getVisiblePages(1, 10), [1, 2, 3, "...", 10]);
  assert.deepEqual(getVisiblePages(10, 10), [1, "...", 8, 9, 10]);
});
