from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np
from google import genai
from google.genai import types

from app.config import settings
from app.models.classification import (
    CpcClassificationResponse,
    RecommendedCpcCode,
)
from app.services.embedding_service import encode_query

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_PATH = BACKEND_DIR / "data" / "cpc_codes.jsonl"
DEFAULT_EMBEDDINGS_PATH = BACKEND_DIR / "data" / "cpc_embeddings.npz"
GOOGLE_PATENTS_BASE_URL = "https://patents.google.com/"

STOPWORDS = {
    "para", "como", "con", "del", "desde", "donde", "el", "en", "entre",
    "esta", "este", "la", "las", "los", "mediante", "por", "que", "segun",
    "sin", "sobre", "sus", "una", "uno", "unos", "the", "and", "for", "from",
    "into", "that", "this", "using", "with",
}


@dataclass(frozen=True)
class CpcCandidate:
    code: str
    title: str
    definition: str
    text: str
    score: float


class ClassificationService:
    def __init__(
        self,
        corpus_path: Path = DEFAULT_CORPUS_PATH,
        embeddings_path: Path = DEFAULT_EMBEDDINGS_PATH,
        gemini_client: Any | None = None,
    ) -> None:
        self.corpus_path = Path(corpus_path)
        self.embeddings_path = Path(embeddings_path)
        self._gemini_client = gemini_client
        self._records: list[dict[str, str]] | None = None
        self._embeddings: np.ndarray | None = None
        self._load_lock = Lock()

    def recommend(self, description: str, top_k: int = 8) -> CpcClassificationResponse:
        candidates = self.retrieve(description, max(top_k, 12))
        if not candidates:
            return CpcClassificationResponse(
                recommended_codes=[],
                keywords=self.extract_keywords(description),
                google_patents_query="",
                notes="No se encontraron candidatos CPC en el corpus local.",
            )

        try:
            generated = self._generate_with_gemini(description, candidates, top_k)
            return self._validate_generated(generated, candidates, description, top_k)
        except Exception as exc:
            logger.warning("Gemini CPC classification failed; using fallback: %s", exc)
            return self._fallback_response(description, candidates, top_k)

    def retrieve(self, description: str, top_k: int = 8) -> list[CpcCandidate]:
        records, embeddings = self._load_index()
        if not records:
            return []

        query_embedding = np.asarray(encode_query(description), dtype=np.float32)
        if query_embedding.ndim != 1 or query_embedding.shape[0] != embeddings.shape[1]:
            raise ValueError("La dimension del embedding de consulta no coincide con el indice CPC")

        scores = embeddings @ query_embedding
        limit = min(max(top_k, 1), len(records))
        indexes = np.argsort(scores)[::-1][:limit]
        return [
            CpcCandidate(
                code=records[index]["code"],
                title=records[index]["title"],
                definition=records[index].get("definition", ""),
                text=records[index]["text"],
                score=float(scores[index]),
            )
            for index in indexes
        ]

    def _load_index(self) -> tuple[list[dict[str, str]], np.ndarray]:
        if self._records is not None and self._embeddings is not None:
            return self._records, self._embeddings

        with self._load_lock:
            if self._records is not None and self._embeddings is not None:
                return self._records, self._embeddings

            records = self._read_corpus()
            embeddings = self._read_or_build_embeddings(records)
            self._records = records
            self._embeddings = embeddings
            return records, embeddings

    def _read_corpus(self) -> list[dict[str, str]]:
        if not self.corpus_path.exists():
            raise FileNotFoundError(
                f"No existe el corpus CPC: {self.corpus_path}. "
                "Cree backend/data/cpc_codes.jsonl antes de iniciar el servicio."
            )

        records: list[dict[str, str]] = []
        with self.corpus_path.open(encoding="utf-8") as corpus:
            for line_number, line in enumerate(corpus, 1):
                if not line.strip():
                    continue
                record = json.loads(line)
                missing = {"code", "title", "text"} - record.keys()
                if missing:
                    raise ValueError(
                        f"Registro CPC incompleto en linea {line_number}: {sorted(missing)}"
                    )
                records.append(record)
        return records

    def _read_or_build_embeddings(self, records: list[dict[str, str]]) -> np.ndarray:
        if self.embeddings_path.exists():
            with np.load(self.embeddings_path) as index:
                embeddings = np.asarray(index["embeddings"], dtype=np.float32)
            if embeddings.ndim != 2 or embeddings.shape[0] != len(records):
                raise ValueError(
                    "El indice CPC no coincide con el corpus. "
                    "Ejecute: python exel/index_cpc_codes.py"
                )
            return embeddings

        logger.info(
            "No existe %s; generando indice CPC en memoria. "
            "Ejecute exel/index_cpc_codes.py para acelerar el arranque.",
            self.embeddings_path,
        )
        if not records:
            return np.empty((0, 0), dtype=np.float32)
        return np.asarray([encode_query(record["text"]) for record in records], dtype=np.float32)

    def _get_gemini_client(self) -> Any:
        if self._gemini_client is None:
            self._gemini_client = genai.Client(api_key=settings.gemini_api_key)
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
                "definition": item.definition,
                "retrieval_score": round(item.score, 4),
            }
            for item in candidates
        ]
        prompt = f"""Analiza la descripcion de una invencion y selecciona hasta {top_k} codigos CPC.

REGLAS:
- Solo puedes devolver codigos presentes en CANDIDATOS.
- No inventes ni completes codigos fuera de la lista.
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

        response = self._get_gemini_client().models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        if not response.text:
            raise ValueError("Gemini devolvio una respuesta vacia")
        return json.loads(response.text)

    def _validate_generated(
        self,
        generated: dict[str, Any],
        candidates: list[CpcCandidate],
        description: str,
        top_k: int,
    ) -> CpcClassificationResponse:
        candidate_map = {candidate.code: candidate for candidate in candidates}
        recommendations: list[RecommendedCpcCode] = []
        seen: set[str] = set()

        for item in generated.get("recommended_codes", []):
            code = str(item.get("code", "")).strip()
            candidate = candidate_map.get(code)
            if not candidate or code in seen:
                continue
            confidence = str(item.get("confidence", "medium")).lower()
            if confidence not in {"high", "medium", "low"}:
                confidence = "medium"
            recommendations.append(
                RecommendedCpcCode(
                    code=code,
                    title=candidate.title,
                    reason=str(item.get("reason") or candidate.definition),
                    confidence=confidence,
                    retrieval_score=round(candidate.score, 4),
                )
            )
            seen.add(code)
            if len(recommendations) >= top_k:
                break

        if not recommendations:
            raise ValueError("Gemini no devolvio codigos CPC validos del conjunto recuperado")

        keywords = self._clean_keywords(generated.get("keywords", []))
        if not keywords:
            keywords = self.extract_keywords(description)
        query = self.build_google_patents_query(
            [item.code for item in recommendations],
            keywords,
        )
        return CpcClassificationResponse(
            recommended_codes=recommendations,
            keywords=keywords,
            google_patents_query=query,
            notes=(
                "Sugerencia preliminar basada en recuperacion semantica local. "
                "Verifique manualmente la clasificacion y los resultados en Google Patents."
            ),
        )

    def _fallback_response(
        self,
        description: str,
        candidates: list[CpcCandidate],
        top_k: int,
    ) -> CpcClassificationResponse:
        selected = candidates[: min(top_k, 5)]
        recommendations = [
            RecommendedCpcCode(
                code=candidate.code,
                title=candidate.title,
                reason=(
                    "El texto recuperado para este codigo es semanticamente cercano: "
                    f"{candidate.definition}"
                ),
                confidence="high" if index < 2 else "medium" if index < 4 else "low",
                retrieval_score=round(candidate.score, 4),
            )
            for index, candidate in enumerate(selected)
        ]
        keywords = self.extract_keywords(description)
        return CpcClassificationResponse(
            recommended_codes=recommendations,
            keywords=keywords,
            google_patents_query=self.build_google_patents_query(
                [item.code for item in recommendations],
                keywords,
            ),
            notes=(
                "Gemini no estuvo disponible; se muestra un resultado de respaldo "
                "basado unicamente en similitud semantica local."
            ),
        )

    @staticmethod
    def _clean_keywords(values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        clean: list[str] = []
        for value in values:
            keyword = re.sub(r"\s+", " ", str(value)).strip(" \"'")
            if keyword and keyword.lower() not in {item.lower() for item in clean}:
                clean.append(keyword[:80])
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
            f"({' OR '.join(quoted_keywords)})"
            if clean_keywords
            else ""
        )
        return " ".join(part for part in (code_expression, keyword_expression) if part)
