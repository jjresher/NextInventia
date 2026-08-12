from unittest.mock import MagicMock

import pytest
from google.genai.errors import ClientError

from app.services.gemini_client import GeminiFallbackClient, ModelLimits


def _client_error(code: int) -> ClientError:
    response = MagicMock()
    response.json.return_value = {
        "error": {"message": "quota exceeded", "status": "RESOURCE_EXHAUSTED"}
    }
    return ClientError(code, response)


CASCADE = [
    ModelLimits(name="model-a", rpm=2, rpd=3),
    ModelLimits(name="model-b", rpm=2, rpd=3),
]


@pytest.fixture
def fake_genai_client(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(
        "app.services.gemini_client.genai.Client",
        lambda api_key: fake,
    )
    return fake


def test_uses_first_model_when_capacity_available(fake_genai_client):
    fake_genai_client.models.generate_content.return_value = MagicMock(text="ok")
    client = GeminiFallbackClient(api_key="fake", cascade=CASCADE)

    result = client.generate("prompt")

    assert result == "ok"
    called_model = fake_genai_client.models.generate_content.call_args.kwargs["model"]
    assert called_model == "model-a"


def test_falls_back_to_next_model_on_real_429(fake_genai_client):
    fake_genai_client.models.generate_content.side_effect = [
        _client_error(429),
        MagicMock(text="from model-b"),
    ]
    client = GeminiFallbackClient(api_key="fake", cascade=CASCADE)

    result = client.generate("prompt")

    assert result == "from model-b"
    assert fake_genai_client.models.generate_content.call_count == 2


def test_non_quota_error_is_not_swallowed(fake_genai_client):
    fake_genai_client.models.generate_content.side_effect = _client_error(400)
    client = GeminiFallbackClient(api_key="fake", cascade=CASCADE)

    with pytest.raises(ClientError) as exc_info:
        client.generate("prompt")

    assert exc_info.value.code == 400
    assert fake_genai_client.models.generate_content.call_count == 1


def test_raises_when_every_model_in_cascade_is_exhausted(fake_genai_client):
    fake_genai_client.models.generate_content.side_effect = _client_error(429)
    client = GeminiFallbackClient(api_key="fake", cascade=CASCADE)

    with pytest.raises(RuntimeError, match="agotaron su cuota"):
        client.generate("prompt")


def test_rpm_exhaustion_skips_model_without_calling_api(fake_genai_client, monkeypatch):
    """Al agotar el RPM local, el modelo se salta sin llamar a la API real
    (ahorra una llamada perdida), y pasa directo al siguiente."""
    current_time = [1_000.0]
    monkeypatch.setattr("time.monotonic", lambda: current_time[0])
    fake_genai_client.models.generate_content.return_value = MagicMock(text="ok")
    client = GeminiFallbackClient(api_key="fake", cascade=CASCADE)

    for _ in range(CASCADE[0].rpm):
        client.generate("prompt")
    assert fake_genai_client.models.generate_content.call_count == CASCADE[0].rpm

    # model-a ya está al tope de RPM (sin avanzar el reloj): debe saltarse
    # directo a model-b sin gastar una llamada real contra model-a.
    fake_genai_client.models.generate_content.reset_mock()
    client.generate("prompt")

    called_model = fake_genai_client.models.generate_content.call_args.kwargs["model"]
    assert called_model == "model-b"
    assert fake_genai_client.models.generate_content.call_count == 1


def test_recovers_first_model_after_rpm_window_clears(fake_genai_client, monkeypatch):
    """Si lo que se saturó fue RPM (ventana de 60s), pasado el minuto debe
    volver a usar el primer modelo de la cascada."""
    current_time = [1_000.0]
    monkeypatch.setattr("time.monotonic", lambda: current_time[0])
    fake_genai_client.models.generate_content.return_value = MagicMock(text="ok")
    client = GeminiFallbackClient(api_key="fake", cascade=CASCADE)

    for _ in range(CASCADE[0].rpm):
        client.generate("prompt")

    current_time[0] += 61  # pasa la ventana de 60s de RPM
    fake_genai_client.models.generate_content.reset_mock()
    client.generate("prompt")

    called_model = fake_genai_client.models.generate_content.call_args.kwargs["model"]
    assert called_model == "model-a"


def test_rpd_exhaustion_persists_after_rpm_window_clears(fake_genai_client, monkeypatch):
    """Si lo que se saturó fue RPD (ventana de 24h), no debe volver al
    primer modelo solo porque pasó el minuto de RPM."""
    current_time = [1_000.0]
    monkeypatch.setattr("time.monotonic", lambda: current_time[0])
    fake_genai_client.models.generate_content.return_value = MagicMock(text="ok")
    client = GeminiFallbackClient(api_key="fake", cascade=CASCADE)

    for _ in range(CASCADE[0].rpd):
        client.generate("prompt")
        current_time[0] += 61  # libera RPM entre llamadas, pero no RPD

    fake_genai_client.models.generate_content.reset_mock()
    client.generate("prompt")

    called_model = fake_genai_client.models.generate_content.call_args.kwargs["model"]
    assert called_model == "model-b"


def test_recovers_first_model_after_rpd_window_clears(fake_genai_client, monkeypatch):
    current_time = [1_000.0]
    monkeypatch.setattr("time.monotonic", lambda: current_time[0])
    fake_genai_client.models.generate_content.return_value = MagicMock(text="ok")
    client = GeminiFallbackClient(api_key="fake", cascade=CASCADE)

    for _ in range(CASCADE[0].rpd):
        client.generate("prompt")
        current_time[0] += 61

    current_time[0] += 86_400  # pasa la ventana de 24h de RPD
    fake_genai_client.models.generate_content.reset_mock()
    client.generate("prompt")

    called_model = fake_genai_client.models.generate_content.call_args.kwargs["model"]
    assert called_model == "model-a"


def test_concurrent_calls_never_exceed_rpm_limit(fake_genai_client):
    """Regresión del bug de race condition: has_capacity() + record_request()
    por separado permitía exceder el límite bajo concurrencia real (threads).
    try_reserve() debe mantenerse exacto incluso con llamadas concurrentes."""
    from concurrent.futures import ThreadPoolExecutor

    fake_genai_client.models.generate_content.return_value = MagicMock(text="ok")
    tight_cascade = [ModelLimits(name="only-model", rpm=5, rpd=1000)]
    client = GeminiFallbackClient(api_key="fake", cascade=tight_cascade)

    def attempt(_):
        try:
            client.generate("prompt")
            return True
        except RuntimeError:
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(attempt, range(20)))

    assert sum(results) == 5
