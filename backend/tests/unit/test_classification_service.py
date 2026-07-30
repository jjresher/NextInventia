import json
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.services.classification_service import ClassificationService


@pytest.fixture
def local_index(tmp_path):
    records = [
        {
            "code": "F02D 41/00",
            "title": "Electrical control",
            "definition": "Electronic engine control using sensors.",
            "text": "electronic engine control sensors",
        },
        {
            "code": "F02D 1/00",
            "title": "Fuel injection control",
            "definition": "Control of fuel injection pumps.",
            "text": "fuel injection pump control",
        },
        {
            "code": "F02D 9/00",
            "title": "Throttle control",
            "definition": "Control by throttling air.",
            "text": "air throttle control",
        },
    ]
    corpus_path = tmp_path / "cpc_codes.jsonl"
    corpus_path.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )
    embeddings_path = tmp_path / "cpc_embeddings.npz"
    np.savez_compressed(
        embeddings_path,
        embeddings=np.asarray(
            [
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float32,
        ),
    )
    return corpus_path, embeddings_path


def test_retrieve_orders_by_cosine_similarity(local_index, monkeypatch):
    monkeypatch.setattr(
        "app.services.classification_service.encode_query",
        lambda _: [0.9, 0.1, 0.0],
    )
    service = ClassificationService(*local_index)

    candidates = service.retrieve("control electronico", top_k=2)

    assert [candidate.code for candidate in candidates] == ["F02D 41/00", "F02D 1/00"]
    assert candidates[0].score == pytest.approx(0.9)


def test_missing_corpus_has_clear_error(tmp_path):
    service = ClassificationService(
        corpus_path=tmp_path / "missing.jsonl",
        embeddings_path=tmp_path / "missing.npz",
    )

    with pytest.raises(FileNotFoundError, match="No existe el corpus CPC"):
        service.retrieve("motor")


def test_gemini_codes_are_limited_to_retrieved_candidates(local_index, monkeypatch):
    monkeypatch.setattr(
        "app.services.classification_service.encode_query",
        lambda _: [1.0, 0.0, 0.0],
    )
    response = MagicMock(
        text=json.dumps(
            {
                "recommended_codes": [
                    {
                        "code": "F02D 41/00",
                        "reason": "Usa control electronico.",
                        "confidence": "high",
                    },
                    {
                        "code": "G06N 99/99",
                        "reason": "Codigo inventado.",
                        "confidence": "high",
                    },
                ],
                "keywords": ["engine control", "sensor"],
            }
        )
    )
    client = MagicMock()
    client.models.generate_content.return_value = response
    service = ClassificationService(*local_index, gemini_client=client)

    result = service.recommend("control electronico del motor", top_k=3)

    assert [item.code for item in result.recommended_codes] == ["F02D 41/00"]
    assert "G06N99/99" not in result.google_patents_query


def test_fallback_when_gemini_fails(local_index, monkeypatch):
    monkeypatch.setattr(
        "app.services.classification_service.encode_query",
        lambda _: [0.8, 0.2, 0.0],
    )
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError("unavailable")
    service = ClassificationService(*local_index, gemini_client=client)

    result = service.recommend("control electronico e inyeccion de combustible", top_k=2)

    assert len(result.recommended_codes) == 2
    assert result.recommended_codes[0].code == "F02D 41/00"
    assert "respaldo" in result.notes


def test_google_patents_query_template():
    query = ClassificationService.build_google_patents_query(
        ["F02D 41/00", "F02D 1/00"],
        ["engine control", "fuel injection"],
    )

    assert query == (
        '(F02D41/00 OR F02D1/00) '
        '("engine control" OR "fuel injection")'
    )
