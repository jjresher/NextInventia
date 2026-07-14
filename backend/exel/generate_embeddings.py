"""
Genera embeddings semánticos para todas las patentes en Supabase.

Pipeline:
    1. Trae patentes con `embedding IS NULL` por páginas.
    2. Concatena título + abstract.
    3. Genera el vector de 384 dim con `paraphrase-multilingual-MiniLM-L12-v2`.
    4. Hace UPDATE de la columna `embedding`.

Idempotente: ya generadas no se vuelven a procesar (filtro `embedding IS NULL`).

Uso (desde `project/backend/` con el venv activo):
    python -m exel.generate_embeddings
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import create_client
from tqdm import tqdm

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
load_dotenv(BACKEND_DIR / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

TABLE = "patentes"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Cuántas filas traemos de Supabase por página.
FETCH_BATCH = 200
# Cuántos textos pasa a la GPU/CPU el modelo en una sola pasada.
ENCODE_BATCH = 64
# Tope de caracteres por documento antes de tokenizar (evita malgastar memoria
# en textos enormes; el modelo trunca a 128 tokens igual).
MAX_CHARS = 2000


def build_text(row: dict) -> str:
    """Combina título + abstract + categoría temática.

    El orden importa: el título va primero (queda menos truncado por el
    límite de tokens del modelo) y `ww` añade la categoría granular
    ("Electrical engineering/Electrical machinery, apparatus, energy"),
    que ayuda a que el embedding capture mejor el tema y mejora tanto la
    búsqueda semántica como el clustering K-means.
    """
    ti = (row.get("ti") or "").strip()
    ab = (row.get("ab") or "").strip()
    ww = (row.get("ww") or "").strip()
    parts = [p for p in (ti, ab, ww) if p]
    text = ". ".join(parts).strip(". ").strip()
    return text[:MAX_CHARS]


def fetch_pending(client, last_id: int) -> list[dict]:
    """Trae el siguiente batch de patentes sin embedding, ordenadas por id."""
    resp = (
        client.table(TABLE)
        .select("id, ti, ab, ww")
        .is_("embedding", "null")
        .gt("id", last_id)
        .order("id")
        .limit(FETCH_BATCH)
        .execute()
    )
    return resp.data or []


def update_embedding(client, patent_id: int, vector: list[float]) -> None:
    """UPDATE patentes SET embedding = :vector WHERE id = :id."""
    client.table(TABLE).update({"embedding": vector}).eq("id", patent_id).execute()


def main() -> None:
    print(f"Cargando modelo {MODEL_NAME}...")
    model = SentenceTransformer(MODEL_NAME)
    print(f"Modelo listo. Dimensión: {model.get_sentence_embedding_dimension()}")

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Total pendiente para barra de progreso (head-only count).
    count_resp = (
        client.table(TABLE).select("id", count="exact").is_("embedding", "null").execute()
    )
    total_pending = count_resp.count or 0
    print(f"Patentes pendientes de embedding: {total_pending}")
    if total_pending == 0:
        print("Nada que hacer.")
        return

    pbar = tqdm(total=total_pending, desc="Embedding", unit="pat")
    last_id = 0
    processed = 0

    while True:
        rows = fetch_pending(client, last_id)
        if not rows:
            break

        texts = [build_text(r) for r in rows]
        vectors = model.encode(
            texts,
            batch_size=ENCODE_BATCH,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        for row, vec in zip(rows, vectors):
            update_embedding(client, row["id"], vec.tolist())
            last_id = row["id"]
            processed += 1
            pbar.update(1)

    pbar.close()
    print(f"Listo. Embeddings generados: {processed}")


if __name__ == "__main__":
    main()
