# Arquitectura y despliegue del MVP con usuarios reales

Fecha de referencia: 4 de septiembre de 2026. Precios en USD, sin impuestos ni conversión a COP.

Este documento propone decisiones y pasos; no implementa cambios ni despliega servicios. Complementa `AUDITORIA_CODIGO.md`. Se revisaron el código y las fuentes oficiales enlazadas. No se midió el consumo real del backend ni se inspeccionó la base desplegada: las estimaciones de capacidad y costo deben validarse antes de contratar o invitar usuarios.

## 1. Qué elegiría para este proyecto

**Empezaría con Railway para frontend y backend, en dos servicios separados, y mantendría Supabase como base de datos.** Usaría una beta cerrada por invitación, una única réplica del backend, CPU —sin GPU— y un contenedor Docker para Python. Mantendría embeddings y clasificación local dentro del backend por ahora.

Esto da un equilibrio razonable entre costo, sencillez y aprendizaje: administras configuración, builds, puertos, dominios, logs, recursos y releases, pero no tienes que operar un servidor Linux, certificados o un clúster.

| Pieza | Elección inicial | Razón |
|---|---|---|
| Frontend Next.js | Servicio Node en Railway | Aprovecha el mismo proyecto de hosting y conserva SSR sin reescribir la aplicación |
| Backend FastAPI + ML | Servicio Docker en Railway | Control sobre dependencias pesadas, modelo y artefactos |
| Base de datos y usuarios | Supabase: PostgreSQL/pgvector + Auth | Ya está integrado para datos; evita operar PostgreSQL y crear autenticación propia |
| Índice CPC | Artefacto inmutable versionado, incluido en la imagen al principio | Es reproducible y cambia poco; evita administrar volúmenes para el primer piloto |
| Generación de texto | Gemini desde el backend, con cuenta y cuotas controladas | Ninguna clave privada en navegador; posibilidad de apagar IA sin apagar búsquedas |
| Código y releases | Repositorio actual, CI y despliegues identificados por commit | Repetibilidad y rollback |

**Alternativa si prefieres máxima comodidad específica de Next.js:** Vercel para el frontend y Railway para el backend. Para un MVP de negocio presupuestaría Vercel Pro; no asumiría que una beta gratuita es automáticamente uso no comercial. Hobby está restringido a uso personal/no comercial. [Planes de Vercel](https://vercel.com/pricing).

**Mi regla de decisión:** si cada dólar cuenta, empieza con ambos servicios en Railway. Si puedes pagar el costo adicional del frontend y valoras mucho la experiencia integrada de Next.js, elige Vercel. No hace falta cambiar el framework ni la base de datos para ninguna de las dos rutas.

## 2. Supuestos del piloto y expectativas

Diseñaría el primer piloto para 10–30 participantes invitados, con unas pocas operaciones pesadas simultáneas. Esto es un objetivo de prueba, no una capacidad garantizada. Cien cuentas registradas no implican cien inferencias concurrentes.

Aceptaría:

- Una sola región y una sola réplica del backend.
- Ventanas cortas y anunciadas de mantenimiento.
- Cuotas por usuario y un mensaje claro de espera/saturación.
- Un mecanismo manual documentado para restaurar o desactivar funcionalidades.

No aceptaría:

- Acceso público ilimitado a Gemini o al clasificador.
- Pérdida de datos privados o mezclas entre usuarios.
- Secretos en el frontend, prompts confidenciales en logs o datos de producción en previews.
- No poder restaurar un backup o identificar qué versión está ejecutándose.

## 3. Por qué este backend no es una API pequeña convencional

El código actual carga `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` y utiliza PyTorch indirectamente. El README estima aproximadamente 400 MB solo para `cpc_embeddings.npy`; además existen el catálogo en objetos Python, el modelo, librerías, buffers temporales y el proceso web.

**400 MB en disco no significa 400 MB de RAM total.** Tampoco `memmap` elimina el costo de leer y multiplicar el índice completo: las páginas accedidas consumen recursos del sistema. Cada proceso adicional puede cargar otro modelo y otro catálogo.

Por eso:

1. No contrataría un servicio de 512 MB para el backend completo esperando que funcione bien.
2. Probaría con un techo inicial de **4 GB de RAM, 1–2 vCPU y un worker de Uvicorn**. Son valores de partida, no requisitos medidos. Después bajaría recursos solo si las pruebas muestran margen.
3. Limitaría inicialmente a **una clasificación/embedding pesado simultáneo**, con cola corta o rechazo controlado; ajustaría a dos únicamente después de medir.
4. No usaría múltiples workers como primera solución al rendimiento: pueden aumentar memoria y competencia de CPU.
5. No cambiaría simplemente `def` por `async def`: el trabajo CPU no se vuelve asíncrono por cambiar la firma y puede bloquear el event loop si se ejecuta directamente allí.
6. Evitaría depender de descargar el modelo por primera vez cuando llegue el primer usuario.

### Prueba de dimensionamiento obligatoria

En el mismo tipo de contenedor que se desplegará, medir:

- RAM al arrancar, después de cargar modelo/CPC y pico bajo concurrencia.
- Tiempo de inicio en frío y reinicio con artefactos disponibles.
- Latencia P50/P95 de búsqueda, detalle, chat y clasificación por separado.
- CPU, tamaño de imagen y tiempo de build.
- Comportamiento con 1, 2 y 5 operaciones pesadas concurrentes.
- Recuperación después de que Gemini tarde demasiado, devuelva 429 o falle.

Reservar aproximadamente 25–30 % de margen sobre el pico observado como política inicial. Si no cabe en el presupuesto, reducir concurrencia o alcance del piloto antes de introducir una infraestructura distribuida.

## 4. Comparación de opciones de hosting

### Opción A — Railway para ambos servicios: mi recomendación de costo/aprendizaje

Usa un proyecto con `frontend` y `backend`, cada uno con su build, variables y despliegue. No ejecutes Node y Python dentro del mismo contenedor solo para aparentar un único servicio.

Railway factura consumo. Hobby tiene un mínimo de USD 5 con ese importe incluido en uso; Pro parte de USD 20 con crédito de uso equivalente. **No se suma siempre la suscripción completa al consumo:** si en Pro consumes USD 32, la base cubierta por el crédito forma parte de esos USD 32. Para un piloto empresarial presupuestaría Pro; para aprendizaje personal, revisar Hobby y sus condiciones al contratar. [Planes de Railway](https://docs.railway.com/pricing/plans).

Ventajas de la decisión: una consola operativa, imágenes portables, logs/variables centralizados y despliegues independientes. Contrapartida: alojar Next como servidor requiere decidir su caché y cuidar su consumo; la factura depende de recursos usados, no solo de visitantes.

### Opción B — Vercel frontend + Railway backend: comodidad de Next.js

Elegiría esta si la simplicidad del frontend pesa más que el ahorro. Configura el root del proyecto Vercel en `frontend`; Python y el CPC se quedan fuera de sus funciones.

Vercel Pro anuncia USD 20/mes como base, con consumo y asientos sujetos al plan. Para el cálculo de este documento se asume un único desarrollador. No es una tarifa plana universal. [Precio de Vercel](https://vercel.com/pricing).

La separación también implica dos paneles y revisar región, variables de preview y timeouts entre proveedores.

### Opción C — Render para backend: alternativa de recursos por instancia

Si prefieres dimensionar una instancia con CPU/RAM concretos, compara Render. Su documentación muestra como referencia un web service de 2 GB por USD 25/mes; confirma la cotización vigente, el workspace y los extras antes de contratar. **Ese tamaño podría no bastar para tu ML**. [Comparación oficial de Render](https://render.com/docs/render-vs-heroku-comparison), [planes de cómputo](https://render.com/docs/compute-plans).

No usaría Render Free para este piloto completo: suspende el servicio tras 15 minutos sin tráfico y no permite disco persistente. Ese reinicio más la carga del modelo perjudica la primera impresión de los usuarios. [Limitaciones oficiales](https://render.com/docs/free).

### Qué dejaría para después

- **VPS + Docker Compose:** útil para aprender Linux, redes, firewall, backups y actualizaciones. No lo elegiría primero si tu prioridad inmediata es feedback del producto. La mensualidad del servidor no incluye tu tiempo de operación.
- **Kubernetes, service mesh y microservicios:** no resuelven el problema actual y agregan demasiadas piezas.
- **Serverless con escalado a cero para todo el ML:** puede funcionar con una preparación específica, pero aquí introduce arranque en frío y empaquetado pesado. Revisarlo después de medir, no como atajo a costo cero.
- **Reescribir el frontend como sitio estático:** las páginas actuales hacen consultas dinámicas en servidor. Un export estático no es equivalente sin cambios. Next puede desplegarse como servidor Node o Docker conservando sus capacidades. [Despliegue de Next.js](https://nextjs.org/docs/app/getting-started/deploying).

## 5. Presupuesto realista y controles

### Tarifas de referencia y ejemplo reproducible

Railway publica RAM a USD 10/GB-mes, CPU a USD 20/vCPU-mes, salida de red a USD 0,05/GB y volumen a USD 0,15/GB-mes. [Tarifas oficiales](https://docs.railway.com/pricing).

Ejemplo ilustrativo para frontend + backend encendidos todo el mes:

```text
2,0 GB de RAM promedio entre ambos servicios × USD 10 = USD 20
0,2 vCPU promedio entre ambos servicios × USD 20     = USD  4
10 GB de salida × USD 0,05                          = USD  0,50
Total ilustrativo de estos recursos                = USD 24,50
```

No es una medición ni una promesa. RAM promedio, picos, CPU, tráfico, builds y artefactos reales pueden cambiar el resultado. La memoria del modelo puede mantener una factura relevante aunque haya pocas solicitudes. Configurar un límite de 4 GB no significa que el ejemplo vaya a consumir exactamente 4 GB todo el mes.

### Escenarios de planificación, no cotizaciones

| Escenario | Aplicaciones web | Supabase | Reserva propuesta para Gemini | Total orientativo mensual |
|---|---:|---:|---:|---:|
| Beta pequeña, todo Railway, corpus que cabe en Free | USD 20–55 | USD 0 | USD 5–10 | USD 25–65 |
| Todo Railway con Supabase Pro | USD 20–55 | Desde USD 25 | USD 5–10 | Desde USD 50–90 |
| Vercel Pro + backend Railway + Supabase Pro | USD 40–70 | Desde USD 25 | USD 5–10 | Desde USD 70–105 |

Las bandas de aplicaciones son estimaciones propias con baja concurrencia y uso moderado; no son precios publicados. No incluyen dominio, SMTP de pago, staging permanente, almacenamiento externo adicional, impuestos, excedentes ni recursos de base de datos superiores al mínimo. Gemini es una **reserva de presupuesto**, no una estimación basada en tokens reales. Su consumo debe calcularse con el modelo finalmente seleccionado, entradas, salidas y reintentos. [Precios de Gemini](https://ai.google.dev/gemini-api/docs/pricing).

### Supabase Free: cuándo sí y cuándo no

Free incluye 500 MB de base de datos, pausa por inactividad y no incluye backups automáticos. Pro parte de USD 25 y ofrece, entre otros, 8 GB de disco y backups diarios con retención de siete días; compute extra/proyectos adicionales cuestan aparte. [Precios y límites de Supabase](https://supabase.com/pricing).

Antes de elegir Free, mide la base completa, incluyendo índices FTS/HNSW y textos extensos. El índice CPC local es distinto del almacenamiento de PostgreSQL. Solo los valores float de 100.000 embeddings de 384 dimensiones ocupan aproximadamente 154 MB, antes de overhead, filas, textos e índices: el número de usuarios no determina si cabe el corpus.

Para una beta con datos desechables y corpus reducido, Free puede ser suficiente. Si los usuarios guardan trabajo que no puedes perder, priorizaría presupuesto para backups y restauración antes que para un frontend más sofisticado.

### Evitar sorpresas de facturación

1. Alertas tempranas, por ejemplo al 50 %, 75 % y 90 % del presupuesto elegido.
2. Límite de gasto del proveedor cuando esté disponible y límites de recursos/concurrencia en la aplicación.
3. Cuotas diarias por usuario y globales para IA, con reserva atómica antes de llamar al proveedor.
4. Tope de tokens de entrada/salida, historial acotado y cantidad de reintentos limitada.
5. Revisar gasto diario durante el primer piloto y semanal después.
6. No confundir una alerta de presupuesto con un corte automático de gasto.

El hard limit de Railway puede dejar workloads fuera de línea: protege el bolsillo a cambio de disponibilidad. Confirma qué partidas cubre; no limita Supabase o Gemini. [Control de costos](https://docs.railway.com/pricing/cost-control).

## 6. Arquitectura mínima que evita problemas futuros

### Mantener un monolito modular

Conserva un solo backend con módulos de patentes, clasificación, chat y, cuando se implemente, autenticación/cuotas. El frontend es otro proceso de presentación, no otro dominio de negocio.

La separación existente entre `routes`, `models` y `services` sirve de punto de partida. Haría pequeñas mejoras, no una reescritura:

- Rutas: validan entrada, identidad y respuesta HTTP.
- Casos de uso/servicios: coordinan búsqueda, chat y clasificación.
- Adaptadores: Supabase, Gemini, embeddings e índice CPC.
- Configuración y lifecycle: construcción y cierre de clientes/modelos.

Usa interfaces pequeñas solo para dependencias externas que necesites simular o sustituir. No crees capas vacías o un framework propio.

### Una fuente de verdad por tipo de estado

| Estado | Ubicación recomendada | Regla |
|---|---|---|
| Patentes, favoritos, feedback e historial persistente | PostgreSQL | Con migraciones y políticas de acceso |
| Identidad | Supabase Auth | Verificación real en backend |
| Cuotas que no deben reiniciarse con un deploy | PostgreSQL inicialmente | Contadores/reservas atómicos y retención limitada |
| Caché descartable y semáforo de la réplica | Memoria | Puede perderse sin perder datos ni presupuesto reservado |
| CPC y modelo | Artefactos versionados | Mismo modelo/preprocesamiento para indexar y consultar |
| Configuración | Variables del servicio | Separar secretos de valores públicos |

No introduciría Redis solo por costumbre. Un contador durable sencillo en PostgreSQL y una sola réplica pueden bastar al principio. Si el volumen lo exige, migrar el control distribuido a un almacén apropiado.

### No acoplar funcionalidades a un proveedor de generación

Mantén un adaptador para Gemini y registra modelo, versión del prompt, versión del índice y modo de respuesta (`local`/`generated`). Una caída de Gemini no debería dejar inutilizable la búsqueda o el detalle de patentes.

No cambies el modelo de embeddings por otro proveedor para ahorrar RAM sin planificar la migración. Los vectores de modelos distintos no son compatibles, aunque tengan igual dimensión: hay que reindexar patentes y CPC, evaluar relevancia y hacer un corte versionado.

## 7. Login, autorización y protección de costos antes de invitar usuarios

### Flujo recomendado

1. El usuario se identifica con Supabase Auth.
2. El navegador obtiene una sesión y envía el access token al backend.
3. FastAPI verifica firma, emisor, audiencia aplicable y expiración mediante una librería confiable; no basta con decodificar el JWT.
4. El backend comprueba que la cuenta está invitada/habilitada y que tiene cuota.
5. Solo entonces consulta datos o llama a Gemini/embeddings.

Supabase documenta los JWT y sus mecanismos de verificación. Elegir el método compatible con las claves del proyecto; no copiar una receta que asuma otro tipo de firma. [JWT de Supabase](https://supabase.com/docs/guides/auth/jwts).

Para correo/magic links, configura un proveedor SMTP y prueba el flujo con alguien que no pertenezca al equipo del proyecto. El SMTP predeterminado de Supabase no entrega a usuarios externos al equipo. Otra opción es OAuth con un proveedor que tus participantes ya usen. [SMTP de Supabase](https://supabase.com/docs/guides/auth/auth-smtp).

### Mínimos de seguridad

- Beta por invitación comprobada en servidor, no solo escondiendo el formulario.
- Rechazo de peticiones sin token y acceso cruzado entre usuarios.
- RLS en tablas privadas y grants mínimos; `user_id` derivado de identidad verificada, no del body.
- Revisar permisos RPC: una función ejecutable por `anon` puede saltarse controles del API. Revocar `PUBLIC`/roles no deseados según la política y probar acceso directo, no solo vía frontend.
- No resolver problemas de permisos cambiando todo a `service_role`: esa clave omite RLS. Separar administración offline y runtime; si una operación privilegiada fuese imprescindible, restringirla y autorizarla explícitamente.
- Contexto del chat reconstruido desde IDs de patentes autorizados, no confiando en texto enviado por el navegador.
- Longitud máxima de inputs/body/historial y límites SQL de `top_k`/pool.
- Rate limiting por usuario además de IP; límites globales, timeouts y una cola acotada.
- HTTPS, CORS de orígenes exactos y errores públicos sin información interna.
- Actualizar dependencias vulnerables y fijar versiones antes del piloto.

Parámetros iniciales sugeridos para experimentar: 10 clasificaciones y 20 turnos de chat por cuenta/día, una operación pesada por cuenta a la vez y un presupuesto global pequeño. No son límites universales; ajústalos con el grupo piloto y mide rechazos útiles versus frustración.

## 8. Privacidad: especial cuidado con invenciones no publicadas

La beta debería usar patentes públicas o ejemplos sintéticos. No invites a pegar material confidencial hasta definir las condiciones con los participantes y los proveedores.

Los términos de Gemini distinguen servicios gratuitos y de pago: en los gratuitos se puede usar contenido para mejorar productos y se advierte no enviar información sensible/confidencial/personal. En los de pago no se usa para ese fin, pero eso no equivale a retención cero ni a procesamiento exclusivamente local. Revisa también restricciones de edad/región para el público elegido. [Términos de Gemini](https://ai.google.dev/gemini-api/terms).

Recomendaciones prácticas:

- Aviso antes del envío: qué sale del sistema y hacia qué proveedor.
- No guardar consultas completas en logs de errores ni herramientas de analítica.
- Para feedback, pedir permiso separado si necesitas conservar la descripción técnica.
- Retención corta y explícita; mecanismo de borrado por usuario.
- No compartir caché de prompts privados entre cuentas.
- No prometer exactitud jurídica ni confidencialidad absoluta por contratar un plan pago.
- Revisar los derechos/licencias del corpus, del catálogo CPC y del modelo antes de distribuirlos en una imagen o bucket.

## 9. Artefactos ML: resolverlo una vez, no en cada deploy

### Mi elección inicial: imagen con artefactos inmutables

Genera el índice CPC fuera del servidor web. Conserva `titles.csv`, `cpc_embeddings.npy` y `manifest.json` como una unidad versionada. Prepara una imagen privada que contenga esa versión y el modelo descargado; las releases del backend pueden reutilizar esa capa.

Ventajas: cada release sabe exactamente qué índice/modelo usa; rollback no depende de un volumen mutable; el arranque no descarga ni genera cientos de MB. Desventajas: imagen/build más pesados y necesidad de comprobar licencia y almacenamiento del registry. Usa caché de capas y no regeneres embeddings en cada commit.

La carpeta está ignorada por Git: **conectar el repositorio al hosting no enviará automáticamente el CPC que existe en tu PC**. Debe haber un mecanismo reproducible que lo incorpore desde un artefacto autorizado. No metas datasets privados en Git ni claves en capas Docker.

### Alternativa: bucket privado + caché local/volumen

Cuando actualizar el índice sin rebuild aporte valor, descarga una versión concreta desde almacenamiento de objetos, valida checksums, descomprime en un directorio temporal y publica la carpeta completa de forma atómica. Mantén una copia anterior hasta validar la nueva.

Si eliges un volumen en Railway, este se monta en runtime, no durante build/pre-deploy; no intentes poblarlo desde una fase donde no existe. Un volumen tampoco es un backup. [Volúmenes de Railway](https://docs.railway.com/volumes).

No asumas que el archivo de 400 MB se puede subir a cualquier tier gratuito: por ejemplo, Supabase Storage Free publica un máximo de 50 MB por archivo. Elige un destino compatible o empaquetado fragmentado controlado. [Límites de Storage](https://supabase.com/pricing).

### Versiones que conservaría juntas

- Commit de aplicación y versión de esquema de base de datos.
- Modelo y revisión exacta de pesos/tokenizador, no solo su nombre.
- Preprocesamiento, dimensión y normalización de embeddings.
- Hash del catálogo, hash del archivo de embeddings y versión del índice.
- Fecha/fuente del corpus y versión de prompt/modelo generativo.

## 10. Ruta de despliegue paso a paso

Los comandos siguientes son ejemplos para un contenedor Linux; no se han ejecutado. Los scripts/variables nuevos que se proponen todavía deben implementarse y probarse.

### Fase 1 — Preparar una release local reproducible

1. Fijar Python/Node y dependencias. Conservar `package-lock.json` y crear un lock Python.
2. Separar dependencias web/ML de Excel, clustering y herramientas de desarrollo cuando las importaciones lo permitan.
3. Crear un `Dockerfile` del backend con CPU-only PyTorch compatible, usuario no root, versiones fijadas y `.dockerignore` para `.env`, entornos locales y exports.
4. Incorporar modelo/CPC por el mecanismo de artefactos elegido; comprobar que pueden abrirse con el usuario del contenedor.
5. Ejecutar tests, lint, build del frontend y smoke test en Linux. El hecho de funcionar en Windows no valida rutas, permisos o wheels Linux.
6. Implementar health checks y un startup controlado. El `/` actual solo dice `ok`: no valida CPC ni modelo.

Mantén un health de proceso barato y uno de readiness. Si CPC es opcional, muestra que esa capacidad está degradada sin bloquear todo el catálogo; si es parte esencial del piloto, no marques ready antes de tenerla disponible. No llames a Gemini ni ejecutes embeddings pesados en cada health check.

### Fase 2 — Preparar la base y autenticación

1. Usar un entorno de prueba independiente, inicialmente local si no alcanza el presupuesto para staging permanente.
2. Corregir la reproducibilidad del esquema antes de clonar producción: falta crear la tabla base; además, la migración 002 referencia `apc`, `ww`, `pd` y `lg_st`, que la 003 incorpora. La secuencia documentada no es suficiente para una base legacy sin esas columnas.
3. Crear una migración inicial/snapshot y una cadena coherente, sin editar a ciegas migraciones ya aplicadas. Probar en una base vacía y con datos representativos.
4. Cargar un subconjunto representativo del corpus si es necesario para el piloto.
5. Verificar RPCs, índices, permisos, login y recuperación de sesión.
6. Realizar un backup y restaurarlo en otro entorno.

No ejecutes scripts de importación o migraciones automáticamente al arrancar cada réplica. Usa un paso de release único y revisable.

### Fase 3 — Backend en Railway

1. Crear proyecto y servicio desde el repositorio con contexto de build `backend` —o la raíz si el diseño del Dockerfile necesita artefactos compartidos—. Documentar la elección.
2. Usar la imagen/Dockerfile probado, sin `--reload`.
3. Configurar una réplica, recursos iniciales y timeout de startup suficiente según la medición.
4. Añadir variables privadas del backend.
5. Generar dominio HTTPS y configurar el puerto que escucha el proceso.
6. Validar salud y endpoints desde fuera, incluyendo llamadas sin autorización que deben fallar.

Comando conceptual de arranque con shell Linux:

```sh
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
```

`PORT` depende de cómo configures el servicio. Si usas la forma JSON de `CMD` de Docker, no se expanden variables de shell automáticamente: usar un entrypoint bien definido o un puerto fijo coordinado con el hosting.

### Fase 4 — Frontend en Railway

1. Crear un segundo servicio desde el mismo repositorio con raíz `frontend`.
2. Instalar con `npm ci` y construir con `npm run build`.
3. Configurar `NEXT_PUBLIC_API_URL` con el dominio HTTPS real **antes del build**.
4. Iniciar en producción con Node, no con `next dev`.
5. Registrar el dominio del frontend como origen permitido en FastAPI.
6. Probar navegación, búsqueda, chat, clasificación y auth desde un navegador externo.

Ejemplo de start command ejecutado mediante shell:

```sh
npm run start -- --hostname 0.0.0.0 --port "${PORT:-3000}"
```

Opcionalmente, preparar `output: "standalone"` para una imagen reducida; requiere empaquetar también los assets de `public` y `.next/static` según el modo elegido. No es necesario para la primera prueba. [Self-hosting de Next.js](https://nextjs.org/docs/app/guides/self-hosting).

### Fase 4 alternativa — Frontend en Vercel

Importar el repositorio, seleccionar `frontend` como root, configurar las variables de Production/Preview por separado y desplegar. No dar a previews de PRs no confiables claves ni acceso a datos de producción. Registrar el dominio de producción y un staging estable; no abrir CORS a todos los dominios de preview.

### Fase 5 — Dominio, región y aceptación

- Empieza con dominios del proveedor si no quieres comprar uno aún; no necesitas dominio personalizado de Supabase para tener tu propio dominio de la aplicación.
- Después, usa `app.tudominio` y `api.tudominio` para desacoplar URLs del proveedor.
- Coloca backend cerca de la región actual de Supabase; mide desde Colombia. La cercanía entre API y DB suele importar más que elegir por intuición la región más cercana al navegador.
- Si usas Vercel, revisa también dónde ejecuta SSR, no solo dónde sirve archivos estáticos.
- Prueba con un usuario externo real, no únicamente con tu sesión de administrador.

## 11. Variables y fronteras de red: errores comunes a evitar

| Variable | Dónde | Estado actual / recomendación |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Frontend, build | Ya existe. Es pública y debe apuntar a una URL alcanzable por el navegador |
| `SUPABASE_URL` | Backend | Ya existe. No basta para conceder permisos |
| `SUPABASE_KEY` | Backend | Ya existe. Auditar privilegios y uso; no publicar claves administrativas |
| `GEMINI_API_KEY` | Backend | Ya existe. Secreta, separada por entorno |
| `FRONTEND_ORIGIN` | Backend | Ya existe. Origen exacto con esquema y puerto si corresponde |
| `ALLOW_LOCAL_NETWORK_ORIGINS` | Backend | Ya existe. `false` en producción |
| `PORT` | Servicios | Debe coincidir con el comando/puerto del contenedor |
| `API_INTERNAL_URL` | Solo servidor Next | Propuesta futura, no implementada: opcional para SSR por red privada |
| `CPC_INDEX_DIR` | Backend | Propuesta futura, no implementada: la ruta actual se calcula desde el código |

No pongas una dirección `*.internal` en `NEXT_PUBLIC_API_URL`: el navegador no tiene acceso a la red privada de Railway. Actualmente SSR y cliente comparten esa variable; usar el endpoint público HTTPS es la opción más simple al inicio. Si más adelante separas la URL interna, limita su uso al código server-only.

El navegador llama directamente al backend para chat/clasificación. Cerrar solo el frontend o proteger solo un preview no protege esa API. Tampoco `localhost` en una variable desplegada apunta a tu computador: según dónde se ejecute, apunta al contenedor o al equipo del visitante.

## 12. Releases, rollback y backups sin infraestructura complicada

### Flujo mínimo de cambios

1. Rama de trabajo y PR.
2. CI: tests Python, lint, typecheck/build de Next y revisión de dependencias/secretos.
3. Smoke test con datos sintéticos en entorno aislado.
4. Paso de migración revisado cuando sea necesario.
5. Despliegue identificado por commit, con health check y validación funcional.
6. Observación de errores, latencia y uso tras el deploy.

No necesitas mantener tres entornos caros encendidos. Sí necesitas separar datos y credenciales: desarrollo local + producción pequeña + staging bajo demanda es un inicio razonable. Configura qué carpetas disparan el despliegue de cada servicio para no reconstruir ML por cambiar texto del frontend.

### Rollback real

Conserva la imagen anterior y su versión de CPC/modelo. Ensaya volver a ella. Un rollback de código no revierte una migración ni recupera filas borradas.

Prefiere migraciones compatibles hacia atrás: añadir campo, desplegar código compatible, completar backfill y retirar el campo antiguo en otra release. Evita mezclar borrados, renombres y cambios de aplicación en un único paso irreversible.

### Backups

Define como objetivos iniciales perder como máximo 24 horas de datos y restaurar en unas horas; son metas a comprobar, no garantías del hosting. Si el trabajo de un usuario exige más, cambia la estrategia antes de recogerlo.

Verifica cobertura y restauración de tablas, esquema, roles/políticas, objetos de almacenamiento y artefactos. Un backup de PostgreSQL no conserva automáticamente archivos de un bucket. Guarda exports de recuperación cifrados fuera del servicio primario y restringe el acceso.

## 13. Qué medir para aprender del MVP

No basta con que el servidor responda HTTP 200. Mediría dos cosas por separado:

**Operación:** errores por endpoint, P95, timeouts, reinicios/OOM, RAM/CPU, cuotas agotadas, costo por operación y tasa de fallback local.

**Producto:** búsquedas completadas, patentes abiertas, recomendaciones útiles según feedback, abandono y recurrencia de uso. Una clasificación técnicamente exitosa puede ser inútil para el usuario.

Guardar eventos mínimos con ID pseudónimo, tipo de acción, duración, resultado y versión del sistema. No enviar descripciones técnicas, tokens, emails o URLs con consultas sensibles a herramientas de analítica por defecto. Para diagnosticar un problema, pedir al usuario un ID de solicitud.

Empezaría con logs estructurados y métricas del hosting más una comprobación externa de disponibilidad. Añadiría una plataforma de errores cuando ayude de verdad; no un stack propio de observabilidad.

## 14. Cuándo cambiar la arquitectura

| Señal observada | Siguiente paso razonable | Lo que no haría automáticamente |
|---|---|---|
| OOM o memoria cerca del límite | Medir/corregir consumo, subir RAM o reducir concurrencia | Multiplicar workers |
| Clasificación ralentiza búsqueda/detalle | Extraer un worker ML y, si la espera lo requiere, jobs persistentes | Dividir toda la aplicación en microservicios |
| Trabajos exceden el timeout HTTP | `202 Accepted`, job ID, cola durable y polling | Mantener requests abiertas indefinidamente |
| Más de una réplica | Cuotas compartidas, estado fuera de memoria, artefactos idénticos | Confiar en el limiter local actual |
| PostgreSQL lento | Revisar planes, índices, counts y caché, luego compute | Cambiar de base de datos sin diagnóstico |
| Ranking CPC lento o malo | Dataset de evaluación y benchmark de ANN frente al escaneo exacto | Comprar una base vectorial nueva sin medir |
| Factura alta con poco tráfico | Identificar RAM residente, builds, tokens y datos transferidos | Migrar a VPS sin contar horas de operación |
| Requisitos de confidencialidad mayores | Evaluación contractual, retención y opciones de procesamiento | Suponer que un plan pago elimina todo riesgo |

Antes de ampliar, prueba una pequeña batería de descripciones con resultados esperados. Mantén identificada la versión del corpus y modelo; no compares la calidad de dos despliegues cuyos índices cambian sin registro.

## 15. Plan para aprender despliegue sin retrasar la validación

### Etapa 1 — Contenedor local

Aprende imagen vs contenedor, capas, `.dockerignore`, variables, puertos, usuario del proceso y persistencia. Objetivo: arrancar el backend desde cero sin depender de archivos ocultos de tu PC.

### Etapa 2 — Un servicio en la nube

Despliega backend, revisa logs, reproduce un error controlado y reinicia. Aprende build vs runtime, health checks, secretos y facturación. Objetivo: explicar qué sucede al hacer deploy y cuánto consume.

### Etapa 3 — Aplicación completa

Añade frontend, HTTPS, CORS y auth. Objetivo: que otra persona entre desde su equipo y complete el flujo sin que debas darle credenciales internas.

### Etapa 4 — Operación segura

Automatiza checks, despliega una release, vuelve a la anterior y restaura un backup en un entorno aislado. Objetivo: saber recuperarte, no solo saber publicar.

### Etapa 5 — Infraestructura más profunda, opcional

Replica el despliegue en un VPS de laboratorio con Docker Compose y reverse proxy. Aprende SSH, firewall, actualizaciones, TLS y monitoreo sin convertir a los usuarios del MVP en la prueba de esa infraestructura.

## 16. Checklist antes de compartir el enlace

- [ ] Reproducir el build en Linux con dependencias fijadas y revisadas.
- [ ] Modelo e índice disponibles y verificados sin depender de la primera visita.
- [ ] Medir RAM/picos y concurrencia en el tamaño contratado.
- [ ] Login de usuario externo e invitaciones verificadas en backend.
- [ ] RPCs y tablas probados con roles sin privilegios; aislamiento de usuarios.
- [ ] Límites de inputs, cuotas, concurrencia, tokens y timeouts activos.
- [ ] Ningún secreto en `NEXT_PUBLIC_*`, Git, imagen o logs.
- [ ] HTTPS y CORS exactos; local network deshabilitado.
- [ ] Comportamiento claro si Gemini, CPC o Supabase fallan.
- [ ] Advertencia de tratamiento de datos antes de enviar contenido a IA.
- [ ] Backup restaurado al menos una vez y rollback ensayado.
- [ ] Alertas de gasto, canal de incidentes y mecanismo para desactivar IA.
- [ ] Métricas/feedback sin capturar invenciones confidenciales por defecto.
- [ ] Capacidad, costos y limitaciones explicados a los participantes.

## Conclusión

**No necesitas infraestructura sofisticada para aprender con usuarios reales. Necesitas un despliegue reproducible, acceso controlado, costos acotados y recuperación comprobada.**

Para tu situación: dos servicios en Railway + Supabase, una sola réplica Python, modelo/índice versionados y beta por invitación. Reserva inicialmente del orden de USD 25–65/mes si el corpus cabe en Free; considera desde USD 50–90/mes con Supabase Pro, sujeto a medición. Si priorizas comodidad de Next.js sobre esa diferencia de costo, mueve únicamente el frontend a Vercel Pro. Deja la separación del ML y la operación de servidores propios para cuando haya una razón medida o una meta concreta de aprendizaje.
