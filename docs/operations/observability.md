# Observabilidad operativa del MVP

La API emite eventos JSON y mantiene métricas acotadas por proceso. `GET /metrics`
devuelve contadores, gauges y duraciones para que el entorno de despliegue los
recoja. Las métricas se reinician al reiniciar el proceso; con varias réplicas, el
monitor externo debe agregarlas.

## Eventos y redacción

Los eventos `request_completed`, `api_error`, `unhandled_error`,
`request_timeout`, `classification_fallback` y `cpc_index_load` incluyen solo
campos operativos permitidos. Las rutas HTTP se registran como plantillas, nunca
con query strings o IDs concretos. No se registran cuerpos, consultas, prompts,
descripciones, claims, respuestas de proveedores, claves ni datos personales.

- `INFO`: requests terminados y carga correcta del índice.
- `WARNING`: errores públicos, timeouts, fallback o índice degradado.
- `ERROR`: errores inesperados; la traza omite el mensaje de la excepción para no
  copiar valores sensibles.

## Señales disponibles

- HTTP: total por método/ruta/status, duración y requests en curso.
- Supabase: total por operación/estado, reintentos, duración y concurrencia.
- Gemini: total/estado, duración, intentos por modelo, rate limits, fallbacks,
  saturación y concurrencia.
- CPC: duración de recuperación, concurrencia, cargas y estado del índice.

Las etiquetas proceden de conjuntos definidos en código. No contienen entradas
del usuario, correlation IDs ni números de patente.

## Alertas mínimas

Configure el monitor del despliegue para avisar cuando ocurra cualquiera de estos
casos:

1. `/health/ready` devuelve 503 durante dos comprobaciones consecutivas.
2. Respuestas HTTP 5xx superan el 5 % durante cinco minutos.
3. Aparece `REQUEST_TIMEOUT`, `EXTERNAL_SERVICE_TIMEOUT` o
   `CHAT_PROVIDER_TIMEOUT` más de tres veces en cinco minutos.
4. Aumentan `provider_saturation_total` o `provider_rate_limits_total` durante
   cinco minutos, o los fallbacks superan el 10 % de las clasificaciones.
5. `cpc_index_loads_total{status!="ready"}` aumenta después de un despliegue.
6. Un gauge de concurrencia permanece por encima de cero sin completarse durante
   más tiempo que `REQUEST_TIMEOUT_SECONDS`.

Ante una alerta, use el `correlation_id` de la respuesta para localizar el evento
sin pedir al usuario que comparta el contenido sensible de su solicitud.
