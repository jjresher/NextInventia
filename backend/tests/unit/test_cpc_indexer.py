import csv

import numpy as np

from app.services.cpc_catalog import load_cpc_catalog
from app.services.embedding_service import EMBEDDING_DIM
from exel.index_cpc_codes import build_index


class FakeEmbeddingModel:
    def get_sentence_embedding_dimension(self):
        return EMBEDDING_DIM

    def encode(self, texts, **_kwargs):
        embeddings = np.zeros((len(texts), EMBEDDING_DIM), dtype=np.float32)
        embeddings[:, 0] = 1.0
        return embeddings


def write_catalog(path):
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(
            ["code", "title", "section", "class", "subclass", "group", "main_group"]
        )
        writer.writerows(
            [
                ["F", "MECHANICAL ENGINEERING", "F", "", "", "", ""],
                ["F02", "COMBUSTION ENGINES", "F", "02", "", "", ""],
                ["F02D", "CONTROLLING ENGINES", "F", "02", "D", "", ""],
                [
                    "F02D41/00",
                    "Electrical control (F02D43/00 takes precedence)",
                    "F",
                    "02",
                    "D",
                    "41",
                    "00",
                ],
                [
                    "F02D41/0002",
                    "{Controlling intake air}",
                    "F",
                    "02",
                    "D",
                    "41",
                    "0002",
                ],
            ]
        )


def test_catalog_builds_semantic_text_and_path(tmp_path):
    source = tmp_path / "source.csv"
    write_catalog(source)

    catalog = load_cpc_catalog(source)
    record = catalog.records[-1]

    assert catalog.eligible_indexes.tolist() == [3, 4]
    assert catalog.semantic_text(record).startswith(
        "Specific concept: Controlling intake air."
    )
    assert [item.code for item in catalog.classification_path(record)] == [
        "F",
        "F02",
        "F02D",
        "F02D 41/00",
    ]


def test_indexer_preserves_row_alignment_and_writes_manifest(tmp_path):
    source = tmp_path / "source.csv"
    output = tmp_path / "index"
    write_catalog(source)

    manifest = build_index(source, output, batch_size=2, model=FakeEmbeddingModel())
    matrix = np.load(output / "cpc_embeddings.npy", mmap_mode="r")
    copied_catalog = load_cpc_catalog(output / "titles.csv")

    assert manifest["row_count"] == 5
    assert manifest["eligible_row_count"] == 2
    assert matrix.shape == (5, EMBEDDING_DIM)
    assert isinstance(matrix, np.memmap)
    assert [record.code for record in copied_catalog.records] == [
        "F",
        "F02",
        "F02D",
        "F02D41/00",
        "F02D41/0002",
    ]
