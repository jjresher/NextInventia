# Frontend de Patentólogos

Interfaz en español para buscar patentes, consultar detalles, conversar sobre
resultados y recomendar códigos CPC. Usa Next.js 16.3.4 (App Router), React
19.2.3, TypeScript y Tailwind CSS 4.

## Ejecución local

Desde `frontend/`:

```powershell
npm ci
npm run dev
```

Abra <http://localhost:3000>. El backend FastAPI debe estar disponible en
`http://localhost:8000`. Consulte el [README principal](../README.md) para
configurar Supabase, Gemini y el índice CPC.

Para otra dirección de backend, cree `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Esta variable es pública y debe contener únicamente la URL base de la API, sin
barra final. Las credenciales de Supabase y Gemini se configuran en el backend.
Reinicie el servidor de desarrollo después de modificarla; en producción,
configúrela antes del build y vuelva a compilar si cambia.

El servidor Next.js consulta el catálogo y el navegador consulta el chat y el
clasificador. Ambos deben poder acceder a la URL configurada. Para usar otra
máquina de la red, sustituya `localhost` por la IP del backend y ejecute:

```powershell
npm run dev -- --hostname 0.0.0.0 --port 3000
```

Configure también CORS y la escucha de red del backend según el README principal.

## Headers de seguridad

`next.config.ts` aplica a todas las rutas una CSP en modo report-only, protección
contra framing y MIME sniffing, una política de referencias y una política de
permisos que deshabilita cámara, geolocalización y micrófono. `connect-src` permite
solo el propio frontend y el origen de `NEXT_PUBLIC_API_URL`; no admite comodines.

La CSP permanece en report-only durante el MVP para observar incompatibilidades
antes de bloquear recursos. Scripts y estilos inline siguen permitidos porque los
usa el runtime de Next.js; deben retirarse de la política cuando se adopten nonces.
HSTS se envía únicamente en builds de producción, donde el sitio debe publicarse
exclusivamente mediante HTTPS. Desarrollo omite HSTS para no forzar HTTPS local.

## Rutas y componentes

| Ruta | Función |
| --- | --- |
| `/` | Catálogo paginado y búsqueda híbrida |
| `/patentes/[id]` | Detalle y patentes similares |
| `/clasificar` | Recomendaciones CPC y ecuación para Google Patents |
| `/acerca` | Información del proyecto |

- `src/lib/api.ts`: cliente HTTP y tipos de respuesta del backend.
- `src/components/FloatingChat.tsx`: chat contextual disponible desde el layout.
- `src/components/SearchContextStore.tsx`: contexto de búsqueda en `sessionStorage`.
- `src/components/CpcClassifier.tsx`: formulario y resultados de clasificación.
- `src/app/globals.css`: estilos globales.
- `src/app/layout.tsx`: navegación, pie, chat y fuente Inter mediante `next/font`.

Sin consulta, el catálogo muestra 20 patentes por página. Una búsqueda muestra
hasta 20 resultados híbridos sin paginación. El chat toma el contexto de la
búsqueda o de la patente abierta. En `sessionStorage` guarda un objeto versionado
con la consulta y los IDs; el backend rehidrata los datos antes de llamar al modelo.

## Verificación y producción

```powershell
npm run lint
npm test
npm run build
npm run test:e2e
npm run start
```

`test` cubre la persistencia y rehidratación segura del contexto del chat.
`test:e2e` levanta el build y una API falsa local para verificar catálogo, detalle,
chat y clasificación sin consumir Supabase ni Gemini. `start` sirve el build de
producción y requiere ejecutar `build` primero.

El build utiliza `next/font/google` para Inter y necesita acceso al proveedor
para descargar la fuente. Si el frontend se publica por HTTPS, configure una
API HTTPS accesible desde el navegador y su origen en `FRONTEND_ORIGIN` del
backend.
