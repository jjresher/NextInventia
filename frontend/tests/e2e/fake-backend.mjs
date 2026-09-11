import { createServer } from "node:http";

const patent = {
  id: 1,
  pn: "TEST-1",
  ti: "Patente de prueba",
  ab: "Un resumen servido por el proveedor falso.",
};

function send(response, payload, status = 200) {
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Origin": "http://127.0.0.1:3100",
    "Content-Length": Buffer.byteLength(body),
    "Content-Type": "application/json",
  });
  response.end(body);
}

createServer((request, response) => {
  if (request.method === "OPTIONS") return send(response, {}, 204);
  if (request.url === "/healthz") return send(response, { status: "ok" });
  if (request.url?.startsWith("/patentes/?")) {
    return send(response, { data: [patent], count: 1, page: 1, page_size: 20 });
  }
  if (request.url === "/patentes/1") return send(response, patent);
  if (request.url === "/patentes/404") {
    return send(response, { detail: "Patente no encontrada" }, 404);
  }
  if (request.url === "/patentes/500") {
    return send(response, { detail: "Fallo temporal" }, 500);
  }
  if (request.url?.startsWith("/patentes/1/similares")) {
    return send(response, { patent_id: 1, data: [], count: 0 });
  }
  if (request.url === "/chat/" && request.method === "POST") {
    return send(response, { reply: "Respuesta del chat falso." });
  }
  if (
    request.url === "/clasificacion/cpc/recommend" &&
    request.method === "POST"
  ) {
    return send(response, {
      recommended_codes: [
        {
          code: "F02D 41/00",
          title: "Control de motores",
          level: "main_group",
          classification_path: [],
          reason: "Coincide con el control descrito.",
          confidence: "high",
          retrieval_score: 0.9,
        },
      ],
      keywords: ["engine control"],
      google_patents_query: "CPC=F02D41/00",
      notes: "Respuesta falsa para E2E.",
      local_fallback: false,
    });
  }
  return send(response, { detail: "Not found" }, 404);
}).listen(8000, "127.0.0.1");
