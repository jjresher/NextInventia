"""Sube `ppulse-merged.csv` a Supabase sin duplicar patentes existentes.

Política de carga:
    1. Lee el CSV unificado generado por `convert_xlsx_to_csv.py`.
    2. Pre-trae el conjunto de `pn` que YA existen en la tabla `patentes`
       (paginado, porque Supabase REST limita a ~1000 filas por request).
    3. Filtra el lote para quedarse solo con los `pn` que faltan.
    4. Inserta por batches con `upsert(..., on_conflict="pn")` como red de
       seguridad (por si entre la lectura y la escritura otra ejecución
       insertó la misma patente).
    5. NO toca las columnas `embedding`, `cluster_id` ni `search_vector`,
       así que las patentes que ya tenían embedding lo conservan.

Uso (desde `project/backend/` con el venv activo):
    python -m exel.upload_to_supabase

Pre-requisitos:
    * Migración 003 aplicada (añade UNIQUE sobre `pn` y columnas nuevas).
    * `ppulse-merged.csv` generado por `convert_xlsx_to_csv.py`.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
CSV_FILE = SCRIPT_DIR / "ppulse-merged.csv"

load_dotenv(BACKEND_DIR / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

TABLE_NAME = "patentes"

# Cuántas filas mandamos por request al insertar.
# Supabase corta los requests REST a ~8s en plan free. Como cada INSERT
# recalcula `search_vector` (GENERATED) y actualiza varios índices GIN/trigram,
# y las patentes traen `descripcion` y `claimen` de varios KB cada una,
# batches grandes pegan el timeout. 25 da margen amplio; si falla, el script
# parte el batch a la mitad y reintenta automáticamente.
BATCH_SIZE = 25

# Límite mínimo al partir batches por timeout. Si una fila sola hace timeout es
# que la fila es patológica (texto muy grande) y se reporta para inspección.
MIN_BATCH_SIZE = 1

# Cuántos `pn` traemos por página al pre-cargar los existentes.
FETCH_PN_PAGE = 1000

# Orden y nombres definitivos en el CSV (debe coincidir con `convert_xlsx_to_csv.py`).
EXPECTED_COLUMNS = [
    "pn",
    "apc",
    "cpc",
    "ic",
    "ww",
    "pd",
    "lg_st",
    "ti",
    "ab",
    "descripcion",
    "claimen",
    "espacenet",
]


def fetch_existing_pns(client) -> set[str]:
    """Trae el conjunto de `pn` ya presentes en la tabla, paginando.

    Importante: paginamos con `.order("id")` para que el offset sea estable
    entre requests (sin orden, PostgREST no garantiza el orden y se podrían
    perder o duplicar filas en distintas páginas).
    """
    existing: set[str] = set()
    offset = 0
    while True:
        resp = (
            client.table(TABLE_NAME)
            .select("pn")
            .order("id")
            .range(offset, offset + FETCH_PN_PAGE - 1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            break
        for r in rows:
            pn = r.get("pn")
            if pn:
                existing.add(pn)
        if len(rows) < FETCH_PN_PAGE:
            break
        offset += FETCH_PN_PAGE
    return existing


def read_csv_rows() -> list[dict]:
    """Lee el CSV completo en memoria (asumiendo decenas de miles de filas)."""
    if not CSV_FILE.exists():
        raise FileNotFoundError(
            f"No existe {CSV_FILE}. Corre primero `python -m exel.convert_xlsx_to_csv`."
        )

    with open(CSV_FILE, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or set(reader.fieldnames) != set(EXPECTED_COLUMNS):
            raise ValueError(
                "El CSV no tiene las columnas esperadas.\n"
                f"  Esperadas: {EXPECTED_COLUMNS}\n"
                f"  Encontradas: {reader.fieldnames}"
            )
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
    return rows


def to_db_payload(row: dict) -> dict:
    """Convierte cadenas vacías a None para que Postgres reciba NULL."""
    return {k: (v if v != "" else None) for k, v in row.items() if k in EXPECTED_COLUMNS}


def _is_timeout_error(err: Exception) -> bool:
    """True si el error de PostgREST es un timeout (statement_timeout / 57014)."""
    msg = str(err).lower()
    return "57014" in msg or "statement timeout" in msg or "timeout" in msg


def _send_batch(client, batch: list[dict]) -> None:
    """Manda un batch como INSERT puro. Como ya filtramos `pn` existentes,
    no necesitamos el sobrecoste del UPSERT (que hace conflict-check)."""
    client.table(TABLE_NAME).insert(batch).execute()


def _send_batch_with_split(client, batch: list[dict], depth: int = 0) -> int:
    """Intenta enviar el batch. Si pega timeout, lo parte a la mitad y
    reintenta recursivamente. Devuelve cuántas filas se insertaron."""
    if not batch:
        return 0
    try:
        _send_batch(client, batch)
        return len(batch)
    except Exception as err:  # noqa: BLE001
        if not _is_timeout_error(err) or len(batch) <= MIN_BATCH_SIZE:
            print(
                f"  ! Falló batch de {len(batch)} filas (depth={depth}): {err}"
            )
            raise
        mid = len(batch) // 2
        print(
            f"  Timeout con batch de {len(batch)}; partiendo en 2 ({mid}/{len(batch) - mid})..."
        )
        a = _send_batch_with_split(client, batch[:mid], depth + 1)
        b = _send_batch_with_split(client, batch[mid:], depth + 1)
        return a + b


def insert_in_batches(client, rows: list[dict]) -> int:
    """Sube `rows` en lotes. Si un lote hace timeout, se parte a la mitad
    automáticamente para no perder el progreso."""
    total = 0
    for start in range(0, len(rows), BATCH_SIZE):
        batch = [to_db_payload(r) for r in rows[start : start + BATCH_SIZE]]
        if not batch:
            continue
        inserted = _send_batch_with_split(client, batch)
        total += inserted
        print(f"  Subidas {total}/{len(rows)} filas...")
    return total


def upload() -> None:
    print(f"Conectando a Supabase y leyendo {CSV_FILE.name}...")
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    rows = read_csv_rows()
    print(f"  CSV: {len(rows)} filas leídas con {len(EXPECTED_COLUMNS)} columnas esperadas.")

    print("Pre-cargando `pn` existentes en la tabla `patentes`...")
    existing = fetch_existing_pns(client)
    print(f"  Ya en BD: {len(existing)} patentes.")

    new_rows = [r for r in rows if r.get("pn") and r["pn"] not in existing]
    skipped = len(rows) - len(new_rows)

    print(f"  Filas con `pn` ya en BD (se ignoran): {skipped}.")
    print(f"  Filas nuevas a insertar: {len(new_rows)}.")

    if not new_rows:
        print("Nada nuevo que subir. OK.")
        return

    inserted = insert_in_batches(client, new_rows)
    print(f"\nListo. Insertadas {inserted} patentes en `{TABLE_NAME}`.")
    print(
        "Tip: si quieres re-generar embeddings y clusters para las nuevas filas, corre:\n"
        "  python -m exel.generate_embeddings\n"
        "  python -m exel.cluster_patentes"
    )


if __name__ == "__main__":
    upload()
