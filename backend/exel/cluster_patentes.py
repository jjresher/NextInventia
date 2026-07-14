"""
Asigna `cluster_id` a cada patente con K-means sobre los embeddings.

Pipeline:
    1. Descarga (id, embedding) de Supabase para todas las patentes con
       embedding ya calculado.
    2. Corre K-means (default K=20) sobre la matriz NxD.
    3. UPDATEa la columna `cluster_id` por lotes.
    4. Imprime resumen: tamaño de cada cluster + 5 títulos representativos.

Uso (desde `project/backend/` con el venv activo):
    python -m exel.cluster_patentes              # K=20 por defecto
    KMEANS_K=30 python -m exel.cluster_patentes   # K personalizado

Requisito previo: haber corrido `generate_embeddings.py`.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict
from pathlib import Path

import httpx
import numpy as np
from dotenv import load_dotenv
from sklearn.cluster import KMeans, MiniBatchKMeans
from supabase import create_client
from tqdm import tqdm

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
load_dotenv(BACKEND_DIR / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
TABLE = "patentes"

K = int(os.getenv("KMEANS_K", "20"))
FETCH_BATCH = 500
MINIBATCH_THRESHOLD = 50_000

# Cuántas patentes metemos en cada `UPDATE ... WHERE id IN (...)`. Más alto =
# menos requests pero URLs más largas (PostgREST manda los valores como query
# params). 100 es un punto medio seguro: ~800 chars por request.
UPDATE_CHUNK = 100

# Reintentos ante caídas de conexión (Supabase corta HTTP/2 cuando el flujo
# está mucho rato abierto, especialmente en plan free).
MAX_RETRIES = 4
RETRY_BASE_DELAY = 2.0  # segundos; crece exponencial: 2, 4, 8, 16


def parse_vector(raw) -> list[float] | None:
    """Supabase devuelve el vector como lista o como string '[0.1,0.2,...]'.
    Normalizamos a lista de floats; si viene None retornamos None."""
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        cleaned = raw.strip().lstrip("[").rstrip("]")
        if not cleaned:
            return None
        return [float(x) for x in cleaned.split(",")]
    raise TypeError(f"Tipo inesperado para embedding: {type(raw)}")


def fetch_all_embeddings(client) -> tuple[list[int], np.ndarray, dict[int, str]]:
    """Devuelve (ids, matriz NxD, mapa id->título) para todas las patentes
    con embedding."""
    ids: list[int] = []
    vectors: list[list[float]] = []
    titles: dict[int, str] = {}

    last_id = 0
    pbar = tqdm(desc="Descargando embeddings", unit="pat")

    while True:
        resp = (
            client.table(TABLE)
            .select("id, ti, embedding")
            .not_.is_("embedding", "null")
            .gt("id", last_id)
            .order("id")
            .limit(FETCH_BATCH)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            break

        for r in rows:
            vec = parse_vector(r.get("embedding"))
            if vec is None:
                continue
            ids.append(r["id"])
            vectors.append(vec)
            titles[r["id"]] = r.get("ti") or ""
            last_id = r["id"]
        pbar.update(len(rows))

    pbar.close()

    if not vectors:
        return [], np.empty((0, 0)), {}

    return ids, np.array(vectors, dtype=np.float32), titles


def _is_transient_error(err: Exception) -> bool:
    """True si el error pinta a problema de red/conexión recuperable."""
    return isinstance(
        err,
        (
            httpx.RemoteProtocolError,
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
        ),
    )


def _update_chunk_with_retry(client, cluster_id: int, ids_chunk: list[int]) -> None:
    """`UPDATE patentes SET cluster_id=:cid WHERE id IN (:ids)` con retry.

    Una sola request actualiza todas las filas del chunk; si la conexión se
    cae, reintentamos con backoff exponencial."""
    delay = RETRY_BASE_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            (
                client.table(TABLE)
                .update({"cluster_id": cluster_id})
                .in_("id", ids_chunk)
                .execute()
            )
            return
        except Exception as err:  # noqa: BLE001
            if not _is_transient_error(err) or attempt == MAX_RETRIES - 1:
                raise
            tqdm.write(
                f"  ! {type(err).__name__}: reintento {attempt + 1}/{MAX_RETRIES - 1} "
                f"en {delay:.0f}s..."
            )
            time.sleep(delay)
            delay *= 2


def update_clusters(client, ids: list[int], labels: np.ndarray) -> None:
    """Sube `cluster_id` a Supabase en bulk.

    Estrategia: agrupamos los ids por su cluster resultante y mandamos un
    UPDATE por cada chunk (~100 ids), no uno por patente. Para 5000 patentes
    y K=20, eso son ~50 requests en lugar de 5000, y se completa en segundos
    en vez de minutos. Además, cada UPDATE es resiliente a caídas de
    conexión (HTTP/2 RST_STREAM, etc.) gracias a `_update_chunk_with_retry`.
    """
    by_cluster: dict[int, list[int]] = defaultdict(list)
    for patent_id, label in zip(ids, labels):
        by_cluster[int(label)].append(int(patent_id))

    pbar = tqdm(total=len(ids), desc="Subiendo cluster_id", unit="pat")
    for cluster_id in sorted(by_cluster.keys()):
        members = by_cluster[cluster_id]
        for start in range(0, len(members), UPDATE_CHUNK):
            chunk = members[start : start + UPDATE_CHUNK]
            _update_chunk_with_retry(client, cluster_id, chunk)
            pbar.update(len(chunk))
    pbar.close()


def print_summary(ids: list[int], labels: np.ndarray, titles: dict[int, str], k: int) -> None:
    """Resumen humano: tamaño de cada cluster + 5 títulos representativos.
    Sirve para etiquetar a mano cada cluster (ej: cluster 0 = biotecnología)."""
    by_cluster: dict[int, list[int]] = defaultdict(list)
    for pid, lab in zip(ids, labels):
        by_cluster[int(lab)].append(pid)

    print("\n" + "=" * 70)
    print(f"Resumen K-means (K={k}, N={len(ids)})")
    print("=" * 70)
    for cid in sorted(by_cluster.keys()):
        members = by_cluster[cid]
        print(f"\n[Cluster {cid:>2}]  size={len(members)}")
        for pid in members[:5]:
            t = titles.get(pid, "")
            print(f"   - #{pid}: {t[:120]}")


def main() -> None:
    print(f"Conectando a Supabase y descargando embeddings...")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    ids, X, titles = fetch_all_embeddings(client)
    n = len(ids)
    if n == 0:
        print("No hay patentes con embedding. Corre primero generate_embeddings.py.")
        return
    if n < K:
        raise SystemExit(f"N ({n}) < K ({K}). Reduce KMEANS_K o genera más embeddings.")

    print(f"Embeddings cargados: shape={X.shape}, K={K}")

    if n >= MINIBATCH_THRESHOLD:
        print("Usando MiniBatchKMeans (N grande)")
        model = MiniBatchKMeans(n_clusters=K, random_state=42, n_init="auto", batch_size=4096)
    else:
        model = KMeans(n_clusters=K, random_state=42, n_init="auto")

    print("Entrenando K-means...")
    labels = model.fit_predict(X)
    print(f"Inercia: {model.inertia_:.2f}")

    print("Subiendo etiquetas a Supabase...")
    update_clusters(client, ids, labels)

    print_summary(ids, labels, titles, K)
    print("\nListo.")


if __name__ == "__main__":
    main()
