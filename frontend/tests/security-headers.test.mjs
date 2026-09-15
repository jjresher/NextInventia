import assert from "node:assert/strict";
import test from "node:test";

import { createSecurityHeaders } from "../src/lib/securityHeaders.mjs";

function asMap(headers) {
  return new Map(headers.map(({ key, value }) => [key, value]));
}

test("restringe framing, referencias, MIME y APIs del navegador", () => {
  const headers = asMap(
    createSecurityHeaders({ apiUrl: "https://api.example.test/v1", isProduction: false })
  );

  assert.equal(headers.get("X-Frame-Options"), "DENY");
  assert.equal(headers.get("X-Content-Type-Options"), "nosniff");
  assert.equal(headers.get("Referrer-Policy"), "strict-origin-when-cross-origin");
  assert.equal(headers.get("Permissions-Policy"), "camera=(), geolocation=(), microphone=()");
  assert.equal(headers.has("Strict-Transport-Security"), false);
});

test("CSP report-only permite exclusivamente self y el origen configurado de API", () => {
  const headers = asMap(
    createSecurityHeaders({ apiUrl: "https://api.example.test/v1", isProduction: true })
  );
  const csp = headers.get("Content-Security-Policy-Report-Only");

  assert.match(csp, /connect-src 'self' https:\/\/api\.example\.test/);
  assert.match(csp, /frame-ancestors 'none'/);
  assert.match(csp, /object-src 'none'/);
  assert.doesNotMatch(csp, /\*/);
  assert.equal(
    headers.get("Strict-Transport-Security"),
    "max-age=31536000; includeSubDomains"
  );
});

test("rechaza protocolos no aptos para connect-src", () => {
  assert.throws(
    () => createSecurityHeaders({ apiUrl: "javascript:alert(1)", isProduction: true }),
    /HTTP o HTTPS/
  );
});
