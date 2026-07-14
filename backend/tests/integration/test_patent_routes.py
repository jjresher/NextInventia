"""
tests/integration/test_patent_routes.py — pruebas de INTEGRACIÓN de los endpoints.

Extiende el test existente en tests/db-patents (test_list_patents_happy_path)
agregando los casos que faltan para cumplir la rúbrica:
  - Cada funcionalidad: mínimo 2 pruebas (happy path + flujo alternativo).
  - Validaciones de FastAPI (422), errores controlados (404), escenarios.

Usa el fixture `client` de conftest.py (TestClient con get_supabase mockeado).
"""

import pytest
from unittest.mock import MagicMock


# ===========================================================================
# GET / — health check
# ===========================================================================

class TestHealthCheck:

    def test_health_check_retorna_200(self, client):
        """Happy path: GET / responde 200."""
        response = client.get("/")
        assert response.status_code == 200

    def test_health_check_retorna_status_ok(self, client):
        """Flujo alternativo: el body confirma que el servicio está activo."""
        body = client.get("/").json()
        assert body["status"] == "ok"
        assert "service" in body


# ===========================================================================
# GET /patentes/ — listado paginado
# ===========================================================================

class TestListPatentes:

    # --- Test existente en tests/db-patents (se conserva sin modificar) ---
    def test_list_patents_happy_path(self, client, mock_supabase):
        """Happy path: respuesta paginada con estructura correcta."""
        fake_rows = [
            {"id": 1, "pn": "US123", "ti": "Invento 1"},
            {"id": 2, "pn": "US456", "ti": "Invento 2"},
        ]
        count_response = MagicMock(count=2)
        data_response = MagicMock(data=fake_rows)

        table = mock_supabase.table.return_value
        table.select.return_value.execute.return_value = count_response
        (table.select.return_value
              .order.return_value
              .range.return_value
              .execute.return_value) = data_response

        response = client.get("/patentes/")

        assert response.status_code == 200
        body = response.json()
        assert body["count"] == 2
        assert body["page"] == 1
        assert body["page_size"] == 50
        assert len(body["data"]) == 2
        assert body["data"][0]["pn"] == "US123"

    def test_list_patentes_tabla_vacia_devuelve_data_vacia(self, client, mock_supabase):
        """Flujo alternativo: tabla vacía → 200 con data=[] y count=0."""
        table = mock_supabase.table.return_value
        table.select.return_value.execute.return_value = MagicMock(count=0)
        (table.select.return_value
              .order.return_value
              .range.return_value
              .execute.return_value) = MagicMock(data=[])

        response = client.get("/patentes/")

        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["count"] == 0

    def test_list_patentes_page_menor_a_1_retorna_422(self, client):
        """Flujo alternativo: page=0 viola ge=1 → FastAPI devuelve 422."""
        response = client.get("/patentes/?page=0")
        assert response.status_code == 422

    def test_list_patentes_page_size_mayor_a_200_retorna_422(self, client):
        """Flujo alternativo: page_size=201 viola le=200 → FastAPI devuelve 422."""
        response = client.get("/patentes/?page_size=201")
        assert response.status_code == 422

    def test_list_patentes_respeta_parametro_page(self, client):
        """El campo page en la respuesta refleja el parámetro recibido."""
        response = client.get("/patentes/?page=3")
        assert response.status_code == 200
        assert response.json()["page"] == 3

    def test_list_patentes_respeta_parametro_page_size(self, client):
        """El campo page_size en la respuesta refleja el parámetro recibido."""
        response = client.get("/patentes/?page_size=10")
        assert response.status_code == 200
        assert response.json()["page_size"] == 10


# ===========================================================================
# GET /patentes/?q= — búsqueda
# ===========================================================================

class TestBuscarPatentes:

    def test_busqueda_con_q_retorna_200_con_estructura_paginada(self, client):
        """Happy path: ?q=motor → 200 con estructura data/count/page/page_size."""
        response = client.get("/patentes/?q=motor")

        assert response.status_code == 200
        body = response.json()
        assert "data" in body
        assert "count" in body

    def test_busqueda_sin_coincidencias_retorna_lista_vacia(self, client, mock_supabase):
        """Flujo alternativo: query sin matches → data=[] y count=0, no error."""
        table = mock_supabase.table.return_value
        (table.select.return_value
              .or_.return_value
              .execute.return_value) = MagicMock(count=0)
        (table.select.return_value
              .or_.return_value
              .order.return_value
              .range.return_value
              .execute.return_value) = MagicMock(data=[])

        response = client.get("/patentes/?q=xyzterminoinexistente")

        assert response.status_code == 200
        body = response.json()
        assert body["data"] == []
        assert body["count"] == 0

    def test_busqueda_con_q_vacio_retorna_422(self, client):
        """
        Flujo alternativo: ?q= viola min_length=1 definido en la ruta → 422.
        FastAPI valida esto automáticamente antes de llamar al servicio.
        """
        response = client.get("/patentes/?q=")
        assert response.status_code == 422

    @pytest.mark.parametrize("query", [
        "US10123456B2",
        "vehículo autónomo",
        "B60W60/00",
    ])
    def test_busqueda_acepta_distintos_formatos_de_query(self, client, query):
        """Escenarios: distintos formatos de query → 200, sin error de servidor."""
        response = client.get(f"/patentes/?q={query}")
        assert response.status_code == 200


# ===========================================================================
# GET /patentes/{id} — detalle de patente
# ===========================================================================

class TestGetPatente:

    def test_get_patente_existente_retorna_200_con_campos_correctos(self, client):
        """Happy path: id=1 existente → 200 con los campos del modelo Patent."""
        response = client.get("/patentes/1")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 1
        assert body["pn"] == "US10123456B2"
        assert body["ti"] == "Autonomous vehicle camera system"
        assert "cpc" in body
        assert "ab" in body

    def test_get_patente_inexistente_retorna_404(self, client, mock_supabase):
        """Flujo alternativo: id sin registro en BD → 404 con mensaje descriptivo."""
        (mock_supabase.table.return_value
             .select.return_value
             .eq.return_value
             .single.return_value
             .execute.return_value) = MagicMock(data=None)

        response = client.get("/patentes/99999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Patente no encontrada"

    def test_get_patente_con_id_no_numerico_retorna_422(self, client):
        """Flujo alternativo: id='abc' no es int → FastAPI devuelve 422."""
        response = client.get("/patentes/abc")
        assert response.status_code == 422

    def test_get_patente_mensaje_404_es_descriptivo(self, client, mock_supabase):
        """El detail del 404 debe ser un string no vacío."""
        (mock_supabase.table.return_value
             .select.return_value
             .eq.return_value
             .single.return_value
             .execute.return_value) = MagicMock(data=None)

        detail = client.get("/patentes/0").json()["detail"]
        assert isinstance(detail, str)
        assert len(detail) > 0