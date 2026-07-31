"""Genera el indice local de embeddings para el corpus CPC.

Ejecutar desde backend:
    python exel/index_cpc_codes.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

BACKEND_DIR = Path(__file__).resolve().parents[1]
CORPUS_PATH = BACKEND_DIR / "data" / "cpc_codes.jsonl"
OUTPUT_PATH = BACKEND_DIR / "data" / "cpc_embeddings.npz"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_records(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"No se encontro el corpus CPC: {path}")
    with path.open(encoding="utf-8") as source:
        records = [json.loads(line) for line in source if line.strip()]
    if not records:
        raise ValueError("El corpus CPC esta vacio")
    return records


def main() -> int:
    records = load_records(CORPUS_PATH)
    model = SentenceTransformer(MODEL_NAME)
    embeddings = model.encode(
        [record["text"] for record in records],
        normalize_embeddings=True,
        show_progress_bar=True,
        convert_to_numpy=True,
    ).astype(np.float32)
    np.savez_compressed(
        OUTPUT_PATH,
        embeddings=embeddings,
        codes=np.asarray([record["code"] for record in records]),
    )
    print(
        f"Indice creado: {OUTPUT_PATH} "
        f"({len(records)} codigos, {embeddings.shape[1]} dimensiones)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
