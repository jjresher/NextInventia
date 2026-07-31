from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CpcClassificationRequest(BaseModel):
    description: str = Field(min_length=1, max_length=6000)
    top_k: int = Field(default=8, ge=1, le=20)

    @field_validator("description")
    @classmethod
    def description_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("La descripcion no puede estar vacia")
        return value


class RecommendedCpcCode(BaseModel):
    code: str
    title: str
    reason: str
    confidence: Literal["high", "medium", "low"]
    retrieval_score: float


class CpcClassificationResponse(BaseModel):
    recommended_codes: list[RecommendedCpcCode]
    keywords: list[str]
    google_patents_query: str
    notes: str
