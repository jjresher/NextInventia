from app.routes.chat import _build_context_block


def test_context_block_empty_when_no_patents():
    assert _build_context_block([]) == ""


def test_context_block_single_patent_includes_full_detail():
    patent = {
        "id": 42,
        "pn": "EP4208230B1",
        "ti": "Sistema de frenado regenerativo",
        "ab": "Un sistema que recupera energía al frenar.",
        "apc": "Bosch",
        "cpc": "B60W10/00",
        "ic": "B60W",
        "pd": "2023-01-15",
        "lg_st": "granted",
        "descripcion": "x" * 5000,
        "claimen": "y" * 4000,
    }

    block = _build_context_block([patent])

    assert "Patente en detalle" in block
    assert "EP4208230B1" in block
    assert "ID: 42" in block
    assert "Bosch" in block
    # Descripción y reivindicaciones se truncan (4000 y 3000 chars respectivamente).
    assert block.count("x") == 4000
    assert block.count("y") == 3000


def test_context_block_multiple_patents_truncates_abstract_and_caps_at_20():
    patents = [
        {"id": i, "pn": f"US{i}", "ti": f"Titulo {i}", "ab": "z" * 500}
        for i in range(1, 25)
    ]

    block = _build_context_block(patents)

    assert "Patentes en contexto" in block
    assert "US1" in block
    assert "US20" in block
    assert "US21" not in block  # se cortan en 20
    # Abstract se trunca a 200 chars en modo multi-patente.
    assert block.count("z") == 200 * 20


def test_context_block_falls_back_to_legacy_columns():
    patent = {
        "id": 1,
        "pn": "US1",
        "ti": "T",
        "pc": "US",  # legacy de `apc`
        "ws": "granted",  # legacy de `ww`
        "ls": "active",  # legacy de `lg_st`
    }

    block = _build_context_block([patent])

    assert "Solicitante: US" in block
    assert "Tema: granted" in block
    assert "Estado: active" in block
