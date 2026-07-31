from app.dependencies import get_classification_service
from app.main import app
from app.models.classification import (
    CpcClassificationResponse,
    RecommendedCpcCode,
)


class FakeClassificationService:
    def recommend(self, description: str, top_k: int) -> CpcClassificationResponse:
        return CpcClassificationResponse(
            recommended_codes=[
                RecommendedCpcCode(
                    code="F02D 41/00",
                    title="Electrical control of combustion engines",
                    reason=f"Aplica al control descrito: {description[:20]}",
                    confidence="high",
                    retrieval_score=0.78,
                )
            ][:top_k],
            keywords=["engine control", "fuel injection"],
            google_patents_query=(
                '(F02D41/00) ("engine control" OR "fuel injection")'
            ),
            notes="Sugerencia preliminar.",
        )


def test_recommend_cpc_happy_path(client):
    app.dependency_overrides[get_classification_service] = FakeClassificationService

    response = client.post(
        "/clasificacion/cpc/recommend",
        json={
            "description": "Sistema electronico que ajusta la inyeccion del motor.",
            "top_k": 8,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_codes"][0]["code"] == "F02D 41/00"
    assert "F02D41/00" in body["google_patents_query"]


def test_recommend_cpc_rejects_blank_description(client):
    app.dependency_overrides[get_classification_service] = FakeClassificationService

    response = client.post(
        "/clasificacion/cpc/recommend",
        json={"description": "   ", "top_k": 8},
    )

    assert response.status_code == 422


def test_recommend_cpc_rejects_invalid_top_k(client):
    app.dependency_overrides[get_classification_service] = FakeClassificationService

    response = client.post(
        "/clasificacion/cpc/recommend",
        json={"description": "Control de motor", "top_k": 0},
    )

    assert response.status_code == 422


def test_cors_allows_local_network_frontend(client):
    response = client.options(
        "/clasificacion/cpc/recommend",
        headers={
            "Origin": "http://192.168.1.3:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://192.168.1.3:3000"


def test_cors_rejects_unconfigured_public_origin(client):
    response = client.options(
        "/clasificacion/cpc/recommend",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
