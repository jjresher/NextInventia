const DEFAULT_API_URL = "http://localhost:8000";

function apiOrigin(apiUrl) {
  const url = new URL(apiUrl || DEFAULT_API_URL);
  if (!new Set(["http:", "https:"]).has(url.protocol)) {
    throw new Error("NEXT_PUBLIC_API_URL debe usar HTTP o HTTPS");
  }
  return url.origin;
}

export function createSecurityHeaders({ apiUrl, isProduction }) {
  const directives = [
    "default-src 'self'",
    "base-uri 'self'",
    `connect-src 'self' ${apiOrigin(apiUrl)}`,
    "font-src 'self' data:",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "img-src 'self' data:",
    "object-src 'none'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
  ];

  const headers = [
    {
      key: "Content-Security-Policy-Report-Only",
      value: directives.join("; "),
    },
    { key: "Permissions-Policy", value: "camera=(), geolocation=(), microphone=()" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
  ];

  if (isProduction) {
    headers.push({
      key: "Strict-Transport-Security",
      value: "max-age=31536000; includeSubDomains",
    });
  }

  return headers;
}
