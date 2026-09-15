import assert from "node:assert/strict";
import test from "node:test";

import {
  getSafeEspacenetUrl,
  getSafeHttpsUrl,
  getSafePatentPath,
} from "../src/lib/urlSafety.mjs";

test("acepta solamente rutas internas con IDs positivos", () => {
  assert.equal(getSafePatentPath("/patentes/42"), "/patentes/42");
  for (const path of [
    "/patentes/0",
    "/patentes/-1",
    "/patentes/1/editar",
    "/patentes/1?next=https://evil.example",
    "//evil.example/patentes/1",
  ]) {
    assert.equal(getSafePatentPath(path), null);
  }
});

test("acepta HTTPS externo sin credenciales", () => {
  assert.equal(getSafeHttpsUrl("https://example.com/path")?.hostname, "example.com");
  for (const url of [
    "http://example.com",
    "javascript:alert(1)",
    "data:text/html,boom",
    "https://example.com@evil.example/path",
    "not-a-url",
  ]) {
    assert.equal(getSafeHttpsUrl(url), null);
  }
});

test("Espacenet solo acepta su host oficial mediante HTTPS", () => {
  assert.equal(
    getSafeEspacenetUrl("https://worldwide.espacenet.com/patent/search?q=test"),
    "https://worldwide.espacenet.com/patent/search?q=test"
  );
  for (const url of [
    "http://worldwide.espacenet.com/patent/search",
    "https://worldwide.espacenet.com.evil.example/patent/search",
    "https://evil.example/?next=worldwide.espacenet.com",
  ]) {
    assert.equal(getSafeEspacenetUrl(url), null);
  }
});
