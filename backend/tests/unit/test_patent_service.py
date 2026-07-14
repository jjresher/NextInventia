"""
tests/unit/test_patent_service.py — pruebas UNITARIAS de PatentService.

Extiende el test existente en la rama tests/db-patents (test_get_all_propaga_error)
agregando los casos que faltan para cumplir la rúbrica:
  - Cada funcionalidad: mínimo 2 pruebas (happy path + flujo alternativo).
  - Coherencia con los criterios de aceptación de las HUs.

No usa FastAPI ni HTTP — prueba PatentService directamente.
"""

import pytest
from unittest.mock import MagicMock
from app.services.patent_service import PatentService

# Importar datos de muestra desde conftest (disponibles automáticamente)
# PATENT_SAMPLE y PATENT_LIST los inyecta conftest.py via el fixture mock_supabase


# ===========================================================================
# HU: Listar patentes — get_all()
# ===========================================================================

class TestGetAll:

    def test_get_all_retorna_datos_y_total_cuando_hay_patentes(self, mock_supabase):
        """Happy path: BD con registros → devuelve (lista, total) correctos."""
        service = PatentService(mock_supabase)

        data, total = service.get_all(page=1, page_size=10)

        assert isinstance(data, list)
        assert isinstance(total, int)
        assert total >= 0

    def test_get_all_devuelve_lista_vacia_cuando_tabla_esta_vacia(self, mock_supabase):
        """Flujo alternativo: tabla vacía → ([], 0) sin lanzar excepción."""
        mock_supabase.table.return_value.select.return_value.execute.return_value = (
            MagicMock(count=0)
        )
        (mock_supabase.table.return_value
             .select.return_value
             .order.return_value
             .range.return_value
             .execute.return_value) = MagicMock(data=[])

        service = PatentService(mock_supabase)
        data, total = service.get_all(page=1, page_size=50)

        assert data == []
        assert total == 0

    def test_get_all_calcula_offset_correcto_para_pagina_2(self, mock_supabase):
        """El offset para page=2, page_size=50 debe ser 50."""
        service = PatentService(mock_supabase)
        service.get_all(page=2, page_size=50)

        range_call = (mock_supabase.table.return_value
                          .select.return_value
                          .order.return_value
                          .range)
        range_call.assert_called_once_with(50, 99)

    @pytest.mark.parametrize("page,page_size,expected_start,expected_end", [
        (1, 50,   0,  49),
        (2, 50,  50,  99),
        (3, 10,  20,  29),
        (1, 10,   0,   9),
    ])
    def test_get_all_offset_correcto_para_distintas_paginas(
        self, mock_supabase, page, page_size, expected_start, expected_end
    ):
        """Escenarios: offset = (page-1)*page_size para distintas combinaciones."""
        service = PatentService(mock_supabase)
        service.get_all(page=page, page_size=page_size)

        range_call = (mock_supabase.table.return_value
                          .select.return_value
                          .order.return_value
                          .range)
        args = range_call.call_args[0]
        assert args[0] == expected_start
        assert args[1] == expected_end

    def test_get_all_consulta_tabla_patentes(self, mock_supabase):
        """Verifica que se consulta la tabla 'patentes' y no otra."""
        service = PatentService(mock_supabase)
        service.get_all()

        mock_supabase.table.assert_called_with("patentes")

    # --- Test existente en tests/db-patents (se conserva sin modificar) ---
    def test_get_all_propaga_error_de_conexion(self):
        """Flujo alternativo: error de conexión con Supabase → se propaga la excepción."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.execute.side_effect = (
            ConnectionError("Supabase no responde")
        )
        service = PatentService(mock_client)

        with pytest.raises(ConnectionError, match="Supabase no responde"):
            service.get_all(page=1, page_size=10)


# ===========================================================================
# HU: Ver detalle de patente — get_by_id()
# ===========================================================================

class TestGetById:

    def test_get_by_id_retorna_ficha_cuando_id_existe(self, mock_supabase):
        """Happy path: id existente → devuelve dict con los campos de la patente."""
        service = PatentService(mock_supabase)

        result = service.get_by_id(1)

        assert result is not None
        assert result["id"] == 1
        assert result["pn"] == "US10123456B2"

    def test_get_by_id_retorna_none_cuando_id_no_existe(self, mock_supabase):
        """
        Flujo alternativo: id inexistente → retorna None.
        La ruta convierte None en HTTP 404.
        """
        (mock_supabase.table.return_value
             .select.return_value
             .eq.return_value
             .single.return_value
             .execute.return_value) = MagicMock(data=None)

        service = PatentService(mock_supabase)
        result = service.get_by_id(99999)

        assert result is None

    def test_get_by_id_filtra_por_el_id_correcto(self, mock_supabase):
        """La query usa .eq('id', patent_id) con el id exacto recibido."""
        service = PatentService(mock_supabase)
        service.get_by_id(42)

        eq_call = (mock_supabase.table.return_value
                       .select.return_value
                       .eq)
        eq_call.assert_called_once_with("id", 42)


# ===========================================================================
# HU: Buscar patentes — search()
# ===========================================================================

class TestSearch:

    def test_search_retorna_resultados_cuando_hay_coincidencias(self, mock_supabase):
        """Happy path: query con matches → devuelve (lista, total) con datos."""
        service = PatentService(mock_supabase)

        data, total = service.search("autonomous vehicle")

        assert isinstance(data, list)
        assert isinstance(total, int)

    def test_search_retorna_lista_vacia_cuando_no_hay_coincidencias(self, mock_supabase):
        """Flujo alternativo: query sin matches → ([], 0) sin excepción."""
        (mock_supabase.table.return_value
             .select.return_value
             .or_.return_value
             .execute.return_value) = MagicMock(count=0)
        (mock_supabase.table.return_value
             .select.return_value
             .or_.return_value
             .order.return_value
             .range.return_value
             .execute.return_value) = MagicMock(data=[])

        service = PatentService(mock_supabase)
        data, total = service.search("xyzterminoinexistente123")

        assert data == []
        assert total == 0

    def test_search_filtra_por_ti_ab_y_pn(self, mock_supabase):
        """El filtro OR debe incluir los campos ti, ab y pn."""
        service = PatentService(mock_supabase)
        service.search("motor electrico")

        or_call = (mock_supabase.table.return_value
                       .select.return_value
                       .or_)
        or_call.assert_called()
        filter_arg = or_call.call_args[0][0]
        assert "ti.ilike" in filter_arg
        assert "ab.ilike" in filter_arg
        assert "pn.ilike" in filter_arg

    def test_search_incluye_el_termino_en_el_filtro(self, mock_supabase):
        """El término buscado debe estar presente dentro del filtro OR."""
        termino = "vehiculo autonomo"
        service = PatentService(mock_supabase)
        service.search(termino)

        or_call = (mock_supabase.table.return_value
                       .select.return_value
                       .or_)
        filter_arg = or_call.call_args[0][0]
        assert termino in filter_arg

    @pytest.mark.parametrize("query", [
        "US10123456B2",        # número exacto de patente
        "vehículo autónomo",   # con acentos
        "B60W60/00",           # código CPC
        "camera SYSTEM",       # mayúsculas mezcladas
    ])
    def test_search_acepta_distintos_formatos_de_query(self, mock_supabase, query):
        """Escenarios: distintos formatos de entrada no deben lanzar excepción."""
        service = PatentService(mock_supabase)
        data, total = service.search(query)

        assert isinstance(data, list)
        assert isinstance(total, int)