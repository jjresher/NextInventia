"""Une los exports de Patentologos en un único CSV listo para subir a Supabase.

Detecta automáticamente todos los archivos:

    project/backend/exel/ppulse-export*.xlsx   -> metadata principal
    project/backend/exel/ppulse-desc*.xlsx     -> descripciones (HTML largo)

Normaliza el esquema (mezcla de exports viejos y nuevos), hace LEFT JOIN
por `pn` con las descripciones y escribe un CSV único:

    project/backend/exel/ppulse-merged.csv

Esquema de salida (compatible con la tabla `patentes` tras migración 003):

    pn, apc, cpc, ic, ww, pd, lg_st, ti, ab, descripcion, claimen, espacenet

El archivo de salida se valida re-leyéndolo: misma forma y mismas celdas.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent

EXPORT_GLOB = "ppulse-export*.xlsx"
DESC_GLOB = "ppulse-desc*.xlsx"
OUTPUT_FILE = SCRIPT_DIR / "ppulse-merged.csv"

# Esquema final: orden y nombres definitivos del CSV.
FINAL_COLUMNS = [
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

# Renombres para soportar tanto los exports nuevos (apc/ww/lg_st/pd) como
# los viejos (pc/ws/ls). En los viejos `pc` no era un equivalente de `apc`
# (era una lista de citas, ver `pruebas.md`); por eso se descarta y NO se
# mete dentro de `apc`.
EXPORT_RENAMES = {
    "claimen*": "claimen",
    "desc": "descripcion",
    "ws": "ww",
    "ls": "lg_st",
}

DESC_RENAMES = {
    "desc": "descripcion",
}


def find_files(pattern: str) -> list[Path]:
    """Devuelve todos los archivos que matchean el patrón, excluyendo el output."""
    return sorted(p for p in SCRIPT_DIR.glob(pattern) if p.is_file())


def looks_like_desc(df: pd.DataFrame) -> bool:
    """Heurística: el archivo de descripciones tiene `desc` y NO tiene `apc`/`ti`."""
    cols = set(df.columns)
    return "desc" in cols and not ({"apc", "ti", "ab"} & cols)


def normalize_export(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas viejas y deja solo las que pertenecen al esquema final."""
    df = df.rename(columns=EXPORT_RENAMES)
    df = df.drop(columns=[c for c in ("pc",) if c in df.columns])  # citas: no se usa

    for col in FINAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df[FINAL_COLUMNS].copy()


def normalize_desc(df: pd.DataFrame) -> pd.DataFrame:
    """Deja solo (pn, descripcion) limpio para el JOIN."""
    df = df.rename(columns=DESC_RENAMES)

    if "pn" not in df.columns:
        raise ValueError("El archivo de descripciones no tiene columna `pn`.")
    if "descripcion" not in df.columns:
        raise ValueError("El archivo de descripciones no tiene columna `desc`.")

    df = df[["pn", "descripcion"]].copy()
    df["descripcion"] = df["descripcion"].fillna("").astype(str)
    return df


def load_exports() -> pd.DataFrame:
    """Carga, normaliza y concatena todos los exports principales."""
    paths = find_files(EXPORT_GLOB)
    if not paths:
        raise FileNotFoundError(
            f"No se encontró ningún archivo {EXPORT_GLOB!r} en {SCRIPT_DIR}"
        )

    frames: list[pd.DataFrame] = []
    for path in paths:
        df = pd.read_excel(path, dtype=str, na_filter=False)
        if looks_like_desc(df):
            print(f"  - {path.name}: parece archivo de descripciones, lo salto aquí.")
            continue
        before = len(df)
        df = normalize_export(df)
        print(f"  - {path.name}: {before} filas -> {len(df.columns)} cols normalizadas.")
        frames.append(df)

    if not frames:
        raise RuntimeError(
            f"Se encontraron archivos {EXPORT_GLOB!r} pero ninguno tenía esquema de export."
        )

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.fillna("").astype(str)
    return merged


def load_descriptions() -> pd.DataFrame:
    """Carga y concatena todos los archivos de descripciones disponibles."""
    paths = find_files(DESC_GLOB)
    if not paths:
        print("  (sin archivos de descripciones; se mantendrán las que ya vengan en el export)")
        return pd.DataFrame(columns=["pn", "descripcion"])

    frames: list[pd.DataFrame] = []
    for path in paths:
        df = pd.read_excel(path, dtype=str, na_filter=False)
        if not looks_like_desc(df):
            print(f"  - {path.name}: no parece archivo de descripciones, lo salto.")
            continue
        df = normalize_desc(df)
        print(f"  - {path.name}: {len(df)} descripciones cargadas.")
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=["pn", "descripcion"])

    descs = pd.concat(frames, ignore_index=True)
    # Quedarse con la última descripción por `pn` (el archivo más reciente gana).
    descs = descs.drop_duplicates(subset=["pn"], keep="last")
    return descs


def merge_export_with_desc(exports: pd.DataFrame, descs: pd.DataFrame) -> pd.DataFrame:
    """LEFT JOIN exports + descs por `pn`, dejando que la desc del archivo
    aparte sobrescriba a la del export solo si existe.

    Importante: para filas sin match en `descs` el merge devuelve NaN; hay
    que convertirlo a "" ANTES de comparar, porque `NaN.astype(str)` en
    pandas da el string `'nan'`, que no es vacío y haría que se perdieran
    las descripciones que ya venían en los exports viejos.
    """
    if descs.empty:
        return exports

    merged = exports.merge(descs, on="pn", how="left", suffixes=("", "_from_desc"))
    desc_col = "descripcion_from_desc"
    if desc_col in merged.columns:
        desc_new = merged[desc_col].fillna("").astype(str)
        desc_orig = merged["descripcion"].fillna("").astype(str)
        # Si la descripción del archivo aparte no está vacía, gana ella;
        # si está vacía, conservamos la del export original (cuando exista).
        merged["descripcion"] = desc_new.where(
            desc_new.str.strip() != "",
            desc_orig,
        )
        merged = merged.drop(columns=[desc_col])
    return merged.fillna("").astype(str)


def deduplicate_pn(df: pd.DataFrame) -> pd.DataFrame:
    """Elimina duplicados por `pn` conservando la última fila (la más rica)."""
    before = len(df)
    df = df.drop_duplicates(subset=["pn"], keep="last")
    after = len(df)
    if before != after:
        print(f"  Deduplicados {before - after} duplicados por `pn`.")
    return df


def write_csv(df: pd.DataFrame) -> None:
    df = df[FINAL_COLUMNS]
    df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
        quoting=csv.QUOTE_ALL,
    )

    verify = pd.read_csv(OUTPUT_FILE, dtype=str, keep_default_na=False)
    if df.shape != verify.shape:
        raise AssertionError(
            f"Round-trip mismatch: dataframe {df.shape} vs csv {verify.shape}"
        )
    if list(df.columns) != list(verify.columns):
        raise AssertionError(
            f"Round-trip mismatch en columnas: {list(df.columns)} vs {list(verify.columns)}"
        )

    diffs = (df.values != verify.values).sum()
    if diffs:
        raise AssertionError(f"{diffs} celdas distintas tras round-trip.")


def convert() -> None:
    print("Cargando exports principales...")
    exports = load_exports()

    print("\nCargando archivos de descripciones (si existen)...")
    descs = load_descriptions()

    print("\nUniendo exports con descripciones por `pn`...")
    merged = merge_export_with_desc(exports, descs)

    print("Deduplicando por `pn`...")
    merged = deduplicate_pn(merged)

    print(f"\nEscribiendo {OUTPUT_FILE.name} ({len(merged)} filas, {len(merged.columns)} cols)...")
    write_csv(merged)
    print("Round-trip verification: OK")
    print(f"Listo. Salida: {OUTPUT_FILE}")


if __name__ == "__main__":
    convert()
