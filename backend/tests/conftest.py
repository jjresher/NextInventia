"""
Usa get_supabase como punto de inyección para que el mock sea lo más simple y estable posible.
Supabase nunca hace llamadas reales: los tests corren sin .env ni red.
"""
import os
os.environ.setdefault("SUPABASE_URL", "http://fake-url-for-testing")
os.environ.setdefault("SUPABASE_KEY", "fake-key-for-testing")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:3000")

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_supabase



# Datos de muestra reutilizables en todos los tests

PATENT_SAMPLE = {
    "id": 1,
    "pn": "US10123456B2",
    "pc": "US",
    "cpc": "B60W60/00",
    "ic": "B60W",
    "ws": "granted",
    "ls": "active",
    "ti": "Autonomous vehicle camera system",
    "ab": "A system and method for camera-based autonomous driving.",
    "descripcion": "The invention relates to self-driving cars using computer vision.",
    "claimen": "1. A method comprising: capturing images with a front camera...",
    "espacenet": "https://worldwide.espacenet.com/patent/US10123456B2",
}

PATENT_LIST = [
    {
        "id": i,
        "pn": f"US{i:08d}B2",
        "pc": "US",
        "cpc": "B60W60/00",
        "ic": "B60W",
        "ws": "granted",
        "ls": "active",
        "ti": f"Patent title number {i}",
        "ab": f"Abstract for patent {i}",
        "espacenet": f"https://espacenet.com/{i}",
    }
    for i in range(1, 11)
]



# Mock de Supabase con todas las cadenas de llamadas preconstruidas

@pytest.fixture
def mock_supabase():
    """
    Mock del cliente Supabase con las cadenas de llamadas del PatentService
    ya configuradas por defecto. Cada test puede sobreescribir lo que necesite.

    Cadenas cubiertas:
      get_all:   .table().select("id", count="exact").execute()             → count
                 .table().select(cols).order().range().execute()             → data
      get_by_id: .table().select().eq().single().execute()                  → single row
      search:    .table().select("id", count="exact").or_().execute()       → count
                 .table().select(cols).or_().order().range().execute()      → data
    """
    mock = MagicMock()

    # Respuestas por defecto
    count_resp = MagicMock(count=len(PATENT_LIST))
    data_resp  = MagicMock(data=PATENT_LIST)
    single_resp = MagicMock(data=PATENT_SAMPLE)

    table = mock.table.return_value

    # --- get_all: count ---
    table.select.return_value.execute.return_value = count_resp

    # --- get_all: data ---
    (table.select.return_value
          .order.return_value
          .range.return_value
          .execute.return_value) = data_resp

    # --- get_by_id ---
    (table.select.return_value
          .eq.return_value
          .single.return_value
          .execute.return_value) = single_resp

    # --- search: count ---
    (table.select.return_value
          .or_.return_value
          .execute.return_value) = count_resp

    # --- search: data ---
    (table.select.return_value
          .or_.return_value
          .order.return_value
          .range.return_value
          .execute.return_value) = data_resp

    return mock



# TestClient con get_supabase sobreescrito

@pytest.fixture
def client(mock_supabase):
    """
    TestClient de FastAPI con get_supabase reemplazado por el mock.
    """
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    yield TestClient(app)
    app.dependency_overrides.clear()
