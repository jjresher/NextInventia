# Clasificación CPC local

Este documento describe la feature que recomienda códigos CPC a partir de una
descripción de invención. Está pensado como contexto técnico para otro agente o
desarrollador que necesite mantenerla, depurarla o extenderla.

## Objetivo

El usuario envía una descripción técnica en español o inglés. El backend:

1. Recupera localmente los códigos CPC semánticamente más cercanos.
2. Envía solo esos candidatos a Gemini.
3. Valida que Gemini no invente códigos.
4. Devuelve códigos recomendados, razones, confianza, jerarquía CPC, palabras
   clave y una ecuación para Google Patents.

Supabase no participa en esta feature. El catálogo y los embeddings viven en
archivos locales.

## Flujo general

```text
titles.csv
    │
    │ index_cpc_codes.py (una sola vez)
    ▼
cpc_embeddings.npy + manifest.json
    │
    │ ClassificationService
    ▼
embedding de consulta → similitud coseno → top 40 candidatos
    │
    ▼
Gemini selecciona y explica → validación backend → respuesta JSON
    │
    └── si Gemini falla: fallback con los mejores candidatos locales
```

## Archivos principales

| Archivo | Responsabilidad |
| --- | --- |
| `app/services/cpc_catalog.py` | Valida y carga `titles.csv`, interpreta niveles CPC, crea rutas jerárquicas y textos semánticos. |
| `exel/index_cpc_codes.py` | Genera offline la matriz completa de embeddings y el manifest. |
| `app/services/classification_service.py` | Carga el índice, recupera candidatos, consulta Gemini, valida y genera el fallback. |
| `app/models/classification.py` | Contratos Pydantic de request y response. |
| `app/routes/classification.py` | Endpoint HTTP y conversión de errores de índice en respuesta 503. |
| `tests/unit/test_cpc_indexer.py` | Pruebas del catálogo y del indexador. |
| `tests/unit/test_classification_service.py` | Pruebas de recuperación, validación y fallback. |

## Dataset y artefactos

El CSV fuente debe tener exactamente estas columnas mínimas:

```text
code,title,section,class,subclass,group,main_group
```

El indexador guarda:

```text
backend/data/cpc_index/
├── titles.csv
├── cpc_embeddings.npy
└── manifest.json
```

- `titles.csv`: copia exacta del catálogo utilizado al indexar.
- `cpc_embeddings.npy`: matriz `float32` normalizada, una fila por cada fila del
  CSV y 384 columnas.
- `manifest.json`: versión del índice, hash SHA-256 del CSV, modelo, dimensión,
  dtype y cantidad de filas.

El orden de las filas es un contrato crítico:

```text
fila N de titles.csv == fila N de cpc_embeddings.npy
```

No se debe ordenar, filtrar o modificar uno de los archivos sin reconstruir el
índice completo. `ClassificationService` valida hash, modelo, filas, forma y
tipo antes de usarlo.

El directorio `data/cpc_index/` está ignorado por Git porque la matriz completa
ocupa aproximadamente 400 MB.

## Generación del índice

Desde `backend/`, con el entorno virtual activo:

```powershell
python exel\index_cpc_codes.py `
  --input "C:\ruta\a\titles.csv" `
  --output data\cpc_index `
  --batch-size 128
```

El script:

1. Valida columnas, títulos vacíos y códigos duplicados.
2. Conserva el título original para mostrarlo en la respuesta.
3. Limpia Unicode, espacios y llaves decorativas para el embedding.
4. Construye contexto verificable de grupo principal, subclase, clase y
   sección.
5. Genera embeddings normalizados con
   `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
6. Escribe primero archivos temporales y solo publica la matriz/manifest al
   terminar correctamente.

Ejemplo de texto que se convierte en embedding:

```text
Specific concept: Controlling intake air.
Main group: Electrical control of supply of combustible mixture.
Subclass: Controlling combustion engines.
Class: Combustion engines.
Section: Mechanical engineering.
```

El modelo es multilingüe, por lo que una consulta en español puede compararse
contra títulos CPC en inglés sin traducir todo el catálogo.

La generación solo se repite si cambia el CSV, el modelo, la dimensión o la
versión interna del índice. En CPU puede tardar varias horas.

## Recuperación local

La recuperación es plana, no jerárquica y no usa SQLite, FAISS ni Supabase.

En la primera petición, `ClassificationService`:

- carga los metadatos de `titles.csv` una sola vez;
- abre `cpc_embeddings.npy` con `numpy.load(..., mmap_mode="r")`;
- conserva ambos objetos en memoria para peticiones posteriores.

Para cada descripción:

```python
query_embedding = encode_query(description)
scores = embeddings @ query_embedding
```

Como los vectores están normalizados, el producto punto equivale a similitud
coseno. Después:

1. Se excluyen sección, clase y subclase; solo se recomiendan símbolos que
   contienen `/` (`main_group` o `subgroup`).
2. `numpy.argpartition` obtiene los 40 mejores sin ordenar las 260 mil
   puntuaciones completas.
3. Solo esos 40 candidatos se envían a Gemini.

La búsqueda plana prioriza cobertura y simplicidad. Si la latencia local se
vuelve problemática, puede sustituirse por FAISS o recuperación jerárquica sin
cambiar el contrato HTTP.

## Gemini y seguridad de la respuesta

Gemini recibe únicamente:

- la descripción del usuario;
- los 40 candidatos recuperados;
- código, título, nivel, ruta y score de cada candidato;
- la instrucción de devolver JSON y no usar códigos externos.

El backend no confía ciegamente en la respuesta. Normaliza espacios y mayúsculas
del código y descarta cualquier recomendación que no exista dentro de los 40
candidatos. También elimina duplicados y limita el resultado a `top_k`.

Si Gemini falla, devuelve JSON inválido o no selecciona ningún código válido,
se utiliza un fallback con hasta cinco candidatos ordenados por similitud local.

## API

```http
POST /clasificacion/cpc/recommend
Content-Type: application/json
```

Request:

```json
{
  "description": "Sistema electrónico que regula la inyección según temperatura y velocidad del motor.",
  "top_k": 8
}
```

Restricciones:

- `description`: 1 a 6000 caracteres y no puede contener solo espacios.
- `top_k`: entre 1 y 20.

Respuesta resumida:

```json
{
  "recommended_codes": [
    {
      "code": "F02D 41/0002",
      "title": "Controlling intake air",
      "level": "subgroup",
      "classification_path": [
        {"code": "F", "title": "...", "level": "section"},
        {"code": "F02", "title": "...", "level": "class"},
        {"code": "F02D", "title": "...", "level": "subclass"},
        {"code": "F02D 41/00", "title": "...", "level": "main_group"}
      ],
      "reason": "...",
      "confidence": "high",
      "retrieval_score": 0.78
    }
  ],
  "keywords": ["engine control", "fuel injection"],
  "google_patents_query": "(F02D41/0002) (\"engine control\" OR \"fuel injection\")",
  "notes": "..."
}
```

Errores relevantes:

- `422`: request vacío o `top_k` fuera de rango.
- `503`: falta un artefacto, el manifest está corrupto o el índice no coincide
  con el CSV/modelo.

## Ejecución y pruebas

El backend necesita `SUPABASE_URL`, `SUPABASE_KEY` y `GEMINI_API_KEY` en `.env`
aunque la recuperación CPC no consulte Supabase.

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Pruebas relevantes:

```powershell
python -m pytest tests\unit\test_cpc_indexer.py
python -m pytest tests\unit\test_classification_service.py
python -m pytest tests\integration\test_classification_routes.py
```

Suite completa:

```powershell
python -m pytest -q
```

## Invariantes para futuras modificaciones

- Mantener el mismo modelo para indexar el catálogo y codificar consultas.
- Mantener vectores normalizados si se usa producto punto como similitud coseno.
- Preservar la alineación exacta entre CSV y matriz.
- No devolver códigos que Gemini haya inventado o que estén fuera del top local.
- No generar embeddings del catálogo durante una petición HTTP.
- Conservar el fallback local cuando Gemini no esté disponible.
- Si cambia el formato de artefactos, incrementar `INDEX_VERSION` y regenerar el
  índice.
- Los códigos CPC son sugerencias preliminares y requieren verificación humana.
