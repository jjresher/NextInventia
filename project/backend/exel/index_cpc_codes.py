"""Construye el indice plano local de todos los simbolos CPC."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.lib.format import open_memmap
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.cpc_catalog import file_sha256, load_cpc_catalog  # noqa: E402
from app.services.embedding_service import EMBEDDING_DIM, MODEL_NAME  # noqa: E402

INDEX_VERSION = 1
CATALOG_FILENAME = "titles.csv"
EMBEDDINGS_FILENAME = "cpc_embeddings.npy"
MANIFEST_FILENAME = "manifest.json"


def build_index(
    input_path: Path,
    output_dir: Path,
    batch_size: int = 128,
    model: Any | None = None,
) -> dict[str, Any]:
    input_path = input_path.resolve()
    output_dir = output_dir.resolve()
    if batch_size < 1:
        raise ValueError("batch_size debe ser mayor que cero")

    catalog = load_cpc_catalog(input_path)
    source_hash = file_sha256(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    catalog_path = output_dir / CATALOG_FILENAME
    embeddings_path = output_dir / EMBEDDINGS_FILENAME
    manifest_path = output_dir / MANIFEST_FILENAME
    temporary_embeddings = output_dir / f"{EMBEDDINGS_FILENAME}.tmp"
    temporary_catalog = output_dir / f"{CATALOG_FILENAME}.tmp"
    temporary_manifest = output_dir / f"{MANIFEST_FILENAME}.tmp"

    temporary_embeddings.unlink(missing_ok=True)
    temporary_catalog.unlink(missing_ok=True)
    temporary_manifest.unlink(missing_ok=True)

    if input_path != catalog_path:
        shutil.copyfile(input_path, temporary_catalog)
        temporary_catalog.replace(catalog_path)

    embedding_model = model or SentenceTransformer(MODEL_NAME)
    embedding_dimension = int(
        embedding_model.get_sentence_embedding_dimension() or EMBEDDING_DIM
    )
    matrix = open_memmap(
        temporary_embeddings,
        mode="w+",
        dtype=np.float32,
        shape=(len(catalog.records), embedding_dimension),
    )

    ranges = range(0, len(catalog.records), batch_size)
    for start in tqdm(ranges, desc="Indexando CPC", unit="lote"):
        stop = min(start + batch_size, len(catalog.records))
        texts = [catalog.semantic_text(record) for record in catalog.records[start:stop]]
        matrix[start:stop] = embedding_model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        ).astype(np.float32, copy=False)
    matrix.flush()
    del matrix
    temporary_embeddings.replace(embeddings_path)

    manifest = {
        "index_version": INDEX_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "source_filename": CATALOG_FILENAME,
        "source_sha256": source_hash,
        "row_count": len(catalog.records),
        "eligible_row_count": int(catalog.eligible_indexes.size),
        "model_name": MODEL_NAME,
        "embedding_dimension": embedding_dimension,
        "embedding_dtype": "float32",
        "embedding_shape": [len(catalog.records), embedding_dimension],
    }
    temporary_manifest.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary_manifest.replace(manifest_path)
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Ruta a titles.csv")
    parser.add_argument(
        "--output",
        type=Path,
        default=BACKEND_DIR / "data" / "cpc_index",
        help="Directorio local del indice",
    )
    parser.add_argument("--batch-size", type=int, default=128)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_index(args.input, args.output, args.batch_size)
    print(
        "Indice creado: "
        f"{manifest['row_count']} codigos, "
        f"{manifest['embedding_dimension']} dimensiones"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
