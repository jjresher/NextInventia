from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
from google.genai import types

from app.config import settings
from app.models.classification import (
    CpcClassificationPathItem,
    CpcClassificationResponse,
    RecommendedCpcCode,
)
from app.services.cpc_catalog import (
    CpcCatalog,
    CpcCatalogError,
    CpcPathItem,
    file_sha256,
    load_cpc_catalog,
)
from app.services.embedding_service import EMBEDDING_DIM, MODEL_NAME, encode_query
from app.services.gemini_client import GeminiFallbackClient

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_INDEX_DIR = BACKEND_DIR / "data" / "cpc_index"
DEFAULT_CATALOG_PATH = DEFAULT_INDEX_DIR / "titles.csv"
DEFAULT_EMBEDDINGS_PATH = DEFAULT_INDEX_DIR / "cpc_embeddings.npy"
DEFAULT_MANIFEST_PATH = DEFAULT_INDEX_DIR / "manifest.json"
INDEX_VERSION = 1
GEMINI_CANDIDATE_COUNT = 40

STOPWORDS = {
    "para", "como", "con", "del", "desde", "donde", "el", "en", "entre",
    "esta", "este", "la", "las", "los", "mediante", "por", "que", "segun",
    "sin", "sobre", "sus", "una", "uno", "unos", "the", "and", "for", "from",
    "into", "that", "this", "using", "with",
}


class CpcIndexError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CpcCandidate:
    raw_code: str
    code: str
    title: str
    level: str
    classification_path: tuple[CpcPathItem, ...]
    semantic_text: str
    score: float


class ClassificationService:
    def __init__(
        self,
        catalog_path: Path = DEFAULT_CATALOG_PATH,
        embeddings_path: Path = DEFAULT_EMBEDDINGS_PATH,
        manifest_path: Path = DEFAULT_MANIFEST_PATH,
        gemini_client: Any | None = None,
    ) -> None:
        self.catalog_path = Path(catalog_path)
        self.embeddings_path = Path(embeddings_path)
        self.manifest_path = Path(manifest_path)
        self._gemini_client = gemini_client
        self._catalog: CpcCatalog | None = None
        self._embeddings: np.ndarray | None = None
        self._load_lock = Lock()

    def recommend(self, description: str, top_k: int = 8) -> CpcClassificationResponse:
        candidates = self.retrieve(description, GEMINI_CANDIDATE_COUNT)
        if not candidates:
            return CpcClassificationResponse(
                recommended_codes=[],
                keywords=self.extract_keywords(description),
                google_patents_query="",
                notes="No se encontraron candidatos CPC en el indice local.",
            )

        try:
            generated = self._generate_with_gemini(description, candidates, top_k)
            return self._validate_generated(generated, candidates, description, top_k)
        except Exception as exc:
            logger.warning("Gemini CPC classification failed; using fallback: %s", exc)
            return self._fallback_response(description, candidates, top_k)

    def retrieve(self, description: str, top_k: int = 40) -> list[CpcCandidate]:
        catalog, embeddings = self._load_index()
        query_embedding = np.asarray(encode_query(description), dtype=np.float32)
        if query_embedding.ndim != 1 or query_embedding.shape[0] != embeddings.shape[1]:
            raise CpcIndexError(
                "La dimension del embedding de consulta no coincide con el indice CPC"
            )

        scores = embeddings @ query_embedding
        eligible_indexes = catalog.eligible_indexes
        limit = min(max(top_k, 1), eligible_indexes.size)
        if limit == 0:
            return []

        eligible_scores = scores[eligible_indexes]
        if limit < eligible_scores.size:
            local_indexes = np.argpartition(eligible_scores, -limit)[-limit:]
        else:
            local_indexes = np.arange(eligible_scores.size)
        local_indexes = local_indexes[
            np.argsort(eligible_scores[local_indexes])[::-1]
        ]
        indexes = eligible_indexes[local_indexes]

        return [
            self._candidate_from_index(catalog, scores, int(index))
            for index in indexes
        ]

    def _candidate_from_index(
        self,
        catalog: CpcCatalog,
        scores: np.ndarray,
        index: int,
    ) -> CpcCandidate:
        record = catalog.records[index]
        return CpcCandidate(
            raw_code=record.code,
            code=record.display_code,
            title=record.title,
            level=record.level,
            classification_path=catalog.classification_path(record),
            semantic_text=catalog.semantic_text(record),
            score=float(scores[index]),
        )

    def _load_index(self) -> tuple[CpcCatalog, np.ndarray]:
        if self._catalog is not None and self._embeddings is not None:
            return self._catalog, self._embeddings

        with self._load_lock:
            if self._catalog is not None and self._embeddings is not None:
                return self._catalog, self._embeddings

            for path in (
                self.catalog_path,
                self.embeddings_path,
                self.manifest_path,
            ):
                if not path.exists():
                    raise CpcIndexError(
                        f"Falta el artefacto CPC {path}. Ejecute exel/index_cpc_codes.py."
                    )

            try:
                manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                catalog = load_cpc_catalog(self.catalog_path)
                embeddings = np.load(
                    self.embeddings_path,
                    mmap_mode="r",
                    allow_pickle=False,
                )
            except (CpcCatalogError, OSError, ValueError, json.JSONDecodeError) as exc:
                raise CpcIndexError(f"No se pudo cargar el indice CPC: {exc}") from exc

            self._validate_index(manifest, catalog, embeddings)
            self._catalog = catalog
            self._embeddings = embeddings
            return catalog, embeddings

    def _validate_index(
        self,
        manifest: dict[str, Any],
        catalog: CpcCatalog,
        embeddings: np.ndarray,
    ) -> None:
        expected_rows = len(catalog.records)
        expected_shape = (expected_rows, EMBEDDING_DIM)
        checks = {
            "version": manifest.get("index_version") == INDEX_VERSION,
            "model": manifest.get("model_name") == MODEL_NAME,
            "rows": manifest.get("row_count") == expected_rows,
            "hash": manifest.get("source_sha256") == file_sha256(self.catalog_path),
            "shape": embeddings.shape == expected_shape,
            "dtype": embeddings.dtype == np.float32,
        }
        failed = [name for name, valid in checks.items() if not valid]
        if failed:
            raise CpcIndexError(
                "El indice CPC no coincide con titles.csv "
                f"({', '.join(failed)}). Ejecute exel/index_cpc_codes.py."
            )

    def _get_gemini_client(self) -> Any:
        if self._gemini_client is None:
            self._gemini_client = GeminiFallbackClient(api_key=settings.gemini_api_key)
        return self._gemini_client

    def _generate_with_gemini(
        self,
        description: str,
        candidates: list[CpcCandidate],
        top_k: int,
    ) -> dict[str, Any]:
        candidate_payload = [
            {
                "code": item.code,
                "title": item.title,
                "level": item.level,
                "classification_path": [
                    {"code": path.code, "title": path.title, "level": path.level}
                    for path in item.classification_path
                ],
                "retrieval_score": round(item.score, 4),
            }
            for item in candidates
        ]
        prompt = f"""Analiza la descripcion de una invencion y selecciona hasta {top_k} codigos CPC.

REGLAS:
- Solo puedes devolver codigos presentes en CANDIDATOS.
- No inventes ni completes codigos fuera de la lista.
- Prefiere el codigo mas especifico respaldado por la descripcion.
- Explica brevemente la relacion tecnica en espanol.
- confidence debe ser high, medium o low.
- Extrae entre 3 y 8 keywords tecnicas, preferiblemente en ingles para Google Patents.
- Devuelve exclusivamente JSON valido con las claves recommended_codes y keywords.

DESCRIPCION:
{description}

CANDIDATOS:
{json.dumps(candidate_payload, ensure_ascii=False)}

FORMATO:
{{"recommended_codes":[{{"code":"F02D 41/00","reason":"...",
"confidence":"high"}}],"keywords":["engine control"]}}"""

        text = self._get_gemini_client().generate(
            prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        if not text:
            raise ValueError("Gemini devolvio una respuesta vacia")
        return json.loads(text)

    def _validate_generated(
        self,
        generated: dict[str, Any],
        candidates: list[CpcCandidate],
        description: str,
        top_k: int,
    ) -> CpcClassificationResponse:
        candidate_map = {
            self._normalize_code(candidate.code): candidate for candidate in candidates
        }
        recommendations: list[RecommendedCpcCode] = []
        seen: set[str] = set()

        for item in generated.get("recommended_codes", []):
            normalized_code = self._normalize_code(str(item.get("code", "")))
            candidate = candidate_map.get(normalized_code)
            if not candidate or normalized_code in seen:
                continue
            confidence = str(item.get("confidence", "medium")).lower()
            if confidence not in {"high", "medium", "low"}:
                confidence = "medium"
            recommendations.append(
                self._to_recommendation(
                    candidate,
                    reason=str(item.get("reason") or candidate.semantic_text),
                    confidence=confidence,
                )
            )
            seen.add(normalized_code)
            if len(recommendations) >= top_k:
                break

        if not recommendations:
            raise ValueError("Gemini no devolvio codigos CPC validos del conjunto recuperado")

        keywords = self._clean_keywords(generated.get("keywords", []))
        if not keywords:
            keywords = self.extract_keywords(description)
        return self._response(recommendations, keywords)

    def _fallback_response(
        self,
        description: str,
        candidates: list[CpcCandidate],
        top_k: int,
    ) -> CpcClassificationResponse:
        selected = candidates[: min(top_k, 5)]
        recommendations = [
            self._to_recommendation(
                candidate,
                reason=(
                    "Este codigo es semanticamente cercano a la descripcion. "
                    f"Contexto CPC: {candidate.semantic_text}"
                ),
                confidence="high" if index < 2 else "medium" if index < 4 else "low",
            )
            for index, candidate in enumerate(selected)
        ]
        return self._response(
            recommendations,
            self.extract_keywords(description),
            notes=(
                "Gemini no estuvo disponible; se muestra un resultado de respaldo "
                "basado unicamente en similitud semantica local."
            ),
        )

    @staticmethod
    def _to_recommendation(
        candidate: CpcCandidate,
        reason: str,
        confidence: str,
    ) -> RecommendedCpcCode:
        return RecommendedCpcCode(
            code=candidate.code,
            title=candidate.title,
            level=candidate.level,
            classification_path=[
                CpcClassificationPathItem(
                    code=item.code,
                    title=item.title,
                    level=item.level,
                )
                for item in candidate.classification_path
            ],
            reason=reason,
            confidence=confidence,
            retrieval_score=round(candidate.score, 4),
        )

    @classmethod
    def _response(
        cls,
        recommendations: list[RecommendedCpcCode],
        keywords: list[str],
        notes: str | None = None,
    ) -> CpcClassificationResponse:
        return CpcClassificationResponse(
            recommended_codes=recommendations,
            keywords=keywords,
            google_patents_query=cls.build_google_patents_query(
                [item.code for item in recommendations],
                keywords,
            ),
            notes=notes or (
                "Sugerencia preliminar basada en recuperacion semantica local. "
                "Verifique manualmente la clasificacion y los resultados en Google Patents."
            ),
        )

    @staticmethod
    def _normalize_code(code: str) -> str:
        return re.sub(r"\s+", "", code).upper()

    @staticmethod
    def _clean_keywords(values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        clean: list[str] = []
        seen: set[str] = set()
        for value in values:
            keyword = re.sub(r"\s+", " ", str(value)).strip(" \"'")
            normalized = keyword.lower()
            if keyword and normalized not in seen:
                clean.append(keyword[:80])
                seen.add(normalized)
            if len(clean) == 8:
                break
        return clean

    @staticmethod
    def extract_keywords(description: str, limit: int = 6) -> list[str]:
        words = re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9-]{2,}", description.lower())
        counts: dict[str, int] = {}
        for word in words:
            normalized = word.translate(str.maketrans("áéíóúüñ", "aeiouun"))
            if normalized in STOPWORDS:
                continue
            counts[normalized] = counts.get(normalized, 0) + 1
        ranked = sorted(counts, key=lambda word: (-counts[word], -len(word), word))
        return ranked[:limit]

    @staticmethod
    def build_google_patents_query(codes: list[str], keywords: list[str]) -> str:
        clean_codes = list(dict.fromkeys(code.replace(" ", "") for code in codes if code))
        clean_keywords = list(
            dict.fromkeys(
                keyword.replace('"', "").strip()
                for keyword in keywords
                if keyword.strip()
            )
        )
        code_expression = f"({' OR '.join(clean_codes)})" if clean_codes else ""
        quoted_keywords = [f'"{keyword}"' for keyword in clean_keywords]
        keyword_expression = (
            f"({' OR '.join(quoted_keywords)})" if clean_keywords else ""
        )
        return " ".join(part for part in (code_expression, keyword_expression) if part)
