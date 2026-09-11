"""Exporta de forma determinista el contrato OpenAPI de FastAPI."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("SUPABASE_URL", "http://openapi.invalid")
os.environ.setdefault("SUPABASE_KEY", "openapi-placeholder")
os.environ.setdefault("GEMINI_API_KEY", "openapi-placeholder")

from app.main import app  # noqa: E402

OUTPUT_PATH = BACKEND_DIR / "openapi.json"


def render_schema() -> str:
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Falla si openapi.json no coincide con los modelos actuales.",
    )
    args = parser.parse_args()
    rendered = render_schema()

    if args.check:
        current = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
        if current != rendered:
            print("openapi.json está desactualizado; ejecute scripts/export_openapi.py")
            return 1
        return 0

    OUTPUT_PATH.write_text(rendered, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
