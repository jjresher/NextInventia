from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REQUIRED_COLUMNS = {
    "code",
    "title",
    "section",
    "class",
    "subclass",
    "group",
    "main_group",
}


class CpcCatalogError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CpcPathItem:
    code: str
    title: str
    level: str


@dataclass(frozen=True, slots=True)
class CpcRecord:
    code: str
    title: str
    section: str
    class_number: str
    subclass_letter: str
    group: str
    main_group: str

    @property
    def display_code(self) -> str:
        if "/" in self.code and len(self.code) > 4:
            return f"{self.code[:4]} {self.code[4:]}"
        return self.code

    @property
    def level(self) -> str:
        if "/" in self.code:
            return "main_group" if self.main_group == "00" else "subgroup"
        if self.subclass_letter:
            return "subclass"
        if self.class_number:
            return "class"
        return "section"

    @property
    def class_code(self) -> str:
        return f"{self.section}{self.class_number}" if self.class_number else ""

    @property
    def subclass_code(self) -> str:
        if not self.subclass_letter:
            return ""
        return f"{self.class_code}{self.subclass_letter}"

    @property
    def main_group_code(self) -> str:
        if not self.group or not self.subclass_code:
            return ""
        return f"{self.subclass_code}{self.group}/00"


@dataclass(slots=True)
class CpcCatalog:
    records: list[CpcRecord]
    eligible_indexes: np.ndarray
    hierarchy_titles: dict[str, str]

    def classification_path(self, record: CpcRecord) -> tuple[CpcPathItem, ...]:
        codes = [record.section, record.class_code, record.subclass_code]
        if record.level == "subgroup":
            codes.append(record.main_group_code)

        levels = ["section", "class", "subclass", "main_group"]
        return tuple(
            CpcPathItem(
                code=format_cpc_code(code),
                title=self.hierarchy_titles[code],
                level=levels[index],
            )
            for index, code in enumerate(codes)
            if code and code in self.hierarchy_titles and code != record.code
        )

    def semantic_text(self, record: CpcRecord) -> str:
        parts = [f"Specific concept: {primary_title(record.title)}."]
        labels_and_codes = (
            ("Main group", record.main_group_code),
            ("Subclass", record.subclass_code),
            ("Class", record.class_code),
            ("Section", record.section),
        )
        for label, code in labels_and_codes:
            if code and code != record.code and code in self.hierarchy_titles:
                parts.append(f"{label}: {primary_title(self.hierarchy_titles[code])}.")
        return " ".join(parts)


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", normalized).strip()


def primary_title(value: str) -> str:
    clean = normalize_title(value)
    primary = clean.split("(", 1)[0].strip(" ;,.")
    return primary or clean


def format_cpc_code(code: str) -> str:
    if "/" in code and len(code) > 4:
        return f"{code[:4]} {code[4:]}"
    return code


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_cpc_catalog(path: Path) -> CpcCatalog:
    if not path.exists():
        raise CpcCatalogError(f"No existe el catalogo CPC: {path}")

    records: list[CpcRecord] = []
    hierarchy_titles: dict[str, str] = {}
    eligible_indexes: list[int] = []
    seen_codes: set[str] = set()

    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise CpcCatalogError(
                f"Faltan columnas requeridas en titles.csv: {sorted(missing)}"
            )

        for line_number, row in enumerate(reader, 2):
            code = row["code"].strip()
            title = row["title"].strip()
            if not code or not title:
                raise CpcCatalogError(
                    f"Codigo o titulo vacio en titles.csv, linea {line_number}"
                )
            if code in seen_codes:
                raise CpcCatalogError(
                    f"Codigo CPC duplicado en titles.csv, linea {line_number}: {code}"
                )
            seen_codes.add(code)

            record = CpcRecord(
                code=code,
                title=title,
                section=row["section"].strip(),
                class_number=row["class"].strip(),
                subclass_letter=row["subclass"].strip(),
                group=row["group"].strip(),
                main_group=row["main_group"].strip(),
            )
            index = len(records)
            records.append(record)
            if record.level in {"section", "class", "subclass", "main_group"}:
                hierarchy_titles[record.code] = record.title
            if "/" in record.code:
                eligible_indexes.append(index)

    if not records:
        raise CpcCatalogError("El catalogo CPC esta vacio")

    return CpcCatalog(
        records=records,
        eligible_indexes=np.asarray(eligible_indexes, dtype=np.int32),
        hierarchy_titles=hierarchy_titles,
    )
