import csv
import json
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.services.classification_service import (
    ClassificationService,
    CpcIndexError,
)
from app.services.cpc_catalog import file_sha256
from app.services.embedding_service import EMBEDDING_DIM, MODEL_NAME


def vector(value: float, axis: int = 0) -> np.ndarray:
    result = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    result[axis] = value
    return result


@pytest.fixture
def local_index(tmp_path):
    catalog_path = tmp_path / "titles.csv"
    rows = [
        ["F", "MECHANICAL ENGINEERING", "F", "", "", "", ""],
        ["F02", "COMBUSTION ENGINES", "F", "02", "", "", ""],
        ["F02D", "CONTROLLING COMBUSTION ENGINES", "F", "02", "D", "", ""],
        [
            "F02D41/00",
            "Electrical control of supply",
            "F",
            "02",
            "D",
            "41",
            "00",
        ],
        [
            "F02D41/0002",
            "Controlling intake air",
            "F",
            "02",
            "D",
            "41",
            "0002",
        ],
        [
            "F02D1/00",
            "Fuel injection control",
            "F",
            "02",
            "D",
            "1",
            "00",
        ],
    ]
    with catalog_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(
            ["code", "title", "section", "class", "subclass", "group", "main_group"]
        )
        writer.writerows(rows)

    embeddings_path = tmp_path / "cpc_embeddings.npy"
    np.save(
        embeddings_path,
        np.asarray(
            [
                vector(0.1),
                vector(0.2),
                vector(1.1),
                vector(0.9),
                vector(1.0),
                vector(0.8),
            ],
            dtype=np.float32,
        ),
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "index_version": 1,
                "source_sha256": file_sha256(catalog_path),
                "row_count": len(rows),
                "model_name": MODEL_NAME,
            }
        ),
        encoding="utf-8",
    )
    return catalog_path, embeddings_path, manifest_path


def query_vector() -> list[float]:
    return vector(1.0).tolist()


def test_retrieve_orders_only_group_codes(local_index, monkeypatch):
    monkeypatch.setattr(
        "app.services.classification_service.encode_query",
        lambda _: query_vector(),
    )
    service = ClassificationService(*local_index)

    candidates = service.retrieve("control electronico", top_k=2)

    assert [candidate.code for candidate in candidates] == [
        "F02D 41/0002",
        "F02D 41/00",
    ]
    assert candidates[0].classification_path[-1].code == "F02D 41/00"
    assert all("/" in candidate.code for candidate in candidates)
    assert isinstance(service._embeddings, np.memmap)


def test_missing_index_has_clear_error(tmp_path):
    service = ClassificationService(
        catalog_path=tmp_path / "missing.csv",
        embeddings_path=tmp_path / "missing.npy",
        manifest_path=tmp_path / "missing.json",
    )

    with pytest.raises(CpcIndexError, match="Falta el artefacto CPC"):
        service.retrieve("motor")


def test_changed_catalog_is_rejected(local_index):
    catalog_path, embeddings_path, manifest_path = local_index
    with catalog_path.open("a", encoding="utf-8") as target:
        target.write("\n")
    service = ClassificationService(catalog_path, embeddings_path, manifest_path)

    with pytest.raises(CpcIndexError, match="hash"):
        service.retrieve("motor")


def test_gemini_codes_are_limited_to_retrieved_candidates(local_index, monkeypatch):
    monkeypatch.setattr(
        "app.services.classification_service.encode_query",
        lambda _: query_vector(),
    )
    response = MagicMock(
        text=json.dumps(
            {
                "recommended_codes": [
                    {
                        "code": "F02D41/0002",
                        "reason": "Usa control electronico.",
                        "confidence": "high",
                    },
                    {
                        "code": "G06N99/99",
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

    assert [item.code for item in result.recommended_codes] == ["F02D 41/0002"]
    assert result.recommended_codes[0].level == "subgroup"
    assert result.recommended_codes[0].classification_path[-1].code == "F02D 41/00"
    assert "G06N99/99" not in result.google_patents_query


def test_fallback_when_gemini_fails(local_index, monkeypatch):
    monkeypatch.setattr(
        "app.services.classification_service.encode_query",
        lambda _: query_vector(),
    )
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError("unavailable")
    service = ClassificationService(*local_index, gemini_client=client)

    result = service.recommend("control electronico e inyeccion", top_k=2)

    assert len(result.recommended_codes) == 2
    assert result.recommended_codes[0].code == "F02D 41/0002"
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
