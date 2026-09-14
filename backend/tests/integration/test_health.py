from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_classification_service, get_supabase
from app.main import create_app


def make_settings(**overrides) -> Settings:
    values = {
        "supabase_url": "http://supabase.test",
        "supabase_key": "fake-key",
        "gemini_api_key": "fake-gemini-key",
        "frontend_origin": "https://frontend.test",
        "app_environment": "test",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_lifespan_reuses_clients_and_closes_supabase_sessions():
    supabase = MagicMock()
    gemini = MagicMock()
    classification = MagicMock()
    supabase_factory = MagicMock(return_value=supabase)
    gemini_factory = MagicMock(return_value=gemini)
    classification_factory = MagicMock(return_value=classification)
    application = create_app(
        make_settings(),
        supabase_factory=supabase_factory,
        gemini_factory=gemini_factory,
        classification_factory=classification_factory,
    )

    with TestClient(application) as client:
        assert client.get("/health/live").status_code == 200
        assert application.state.supabase is supabase
        assert application.state.gemini is gemini
        assert application.state.classification_service is classification

    supabase_factory.assert_called_once_with("http://supabase.test", "fake-key")
    gemini_factory.assert_called_once_with("fake-gemini-key")
    classification_factory.assert_called_once_with(gemini)
    supabase._postgrest.aclose.assert_called_once_with()
    supabase.auth.close.assert_called_once_with()


def test_liveness_does_not_probe_optional_dependencies():
    application = create_app(make_settings())
    unavailable_supabase = MagicMock()
    unavailable_supabase.table.side_effect = ConnectionError("offline")
    unavailable_index = MagicMock()
    unavailable_index.check_index.side_effect = OSError("missing")
    application.dependency_overrides[get_supabase] = lambda: unavailable_supabase
    application.dependency_overrides[get_classification_service] = lambda: unavailable_index

    with TestClient(application) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    unavailable_supabase.table.assert_not_called()
    unavailable_index.check_index.assert_not_called()


def test_readiness_identifies_each_unavailable_dependency():
    application = create_app(make_settings())
    unavailable_supabase = MagicMock()
    unavailable_supabase.table.side_effect = ConnectionError("offline")
    unavailable_index = MagicMock()
    unavailable_index.check_index.side_effect = OSError("missing")
    application.dependency_overrides[get_supabase] = lambda: unavailable_supabase
    application.dependency_overrides[get_classification_service] = lambda: unavailable_index

    with TestClient(application) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "configuration": "ok",
            "gemini": "configured",
            "supabase": "unavailable",
            "cpc_index": "unavailable",
        },
    }


def test_readiness_reports_ready_when_all_checks_pass():
    application = create_app(make_settings())
    supabase = MagicMock()
    classification = MagicMock()
    application.dependency_overrides[get_supabase] = lambda: supabase
    application.dependency_overrides[get_classification_service] = lambda: classification

    with TestClient(application) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    supabase.table.return_value.select.return_value.limit.assert_called_once_with(1)
    classification.check_index.assert_called_once_with()


def test_production_never_enables_private_network_cors_regex():
    application = create_app(
        make_settings(
            app_environment="production",
            allow_local_network_origins=True,
        )
    )

    with TestClient(application) as client:
        response = client.options(
            "/patentes/",
            headers={
                "Origin": "http://192.168.1.20:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
