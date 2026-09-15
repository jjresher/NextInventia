from unittest.mock import MagicMock

import app.routes.chat as chat_module
from google.genai.errors import ClientError


def test_chat_happy_path(client, monkeypatch):
    fake_client = MagicMock()
    fake_client.generate.return_value = "Respuesta de PatentBot."
    monkeypatch.setattr(chat_module, "_client", fake_client)

    response = client.post("/chat/", json={"message": "Hola"})

    assert response.status_code == 200
    assert response.json() == {"reply": "Respuesta de PatentBot."}
    fake_client.generate.assert_called_once()


def test_chat_sends_history_as_content_turns(client, monkeypatch):
    fake_client = MagicMock()
    fake_client.generate.return_value = "ok"
    monkeypatch.setattr(chat_module, "_client", fake_client)

    response = client.post(
        "/chat/",
        json={
            "message": "¿Y la segunda?",
            "history": [
                {"role": "user", "content": "Explícame la primera patente"},
                {"role": "model", "content": "Es sobre un sistema de frenado."},
            ],
        },
    )

    assert response.status_code == 200
    contents = fake_client.generate.call_args.args[0]
    assert len(contents) == 3  # 2 turnos de historial + el mensaje nuevo
    assert contents[0].role == "user"
    assert contents[1].role == "model"
    assert contents[2].role == "user"
    assert contents[2].parts[0].text == "¿Y la segunda?"


def test_chat_includes_single_patent_context_in_system_instruction(client, monkeypatch):
    fake_client = MagicMock()
    fake_client.generate.return_value = "ok"
    monkeypatch.setattr(chat_module, "_client", fake_client)

    response = client.post(
        "/chat/",
        json={
            "message": "¿De qué trata?",
            "patents_context": [
                {
                    "id": 42,
                    "pn": "EP4208230B1",
                    "ti": "Sistema de frenado regenerativo",
                    "ab": "Un sistema que recupera energía al frenar.",
                }
            ],
        },
    )

    assert response.status_code == 200
    config = fake_client.generate.call_args.kwargs["config"]
    assert "EP4208230B1" in config.system_instruction
    assert "Patente en detalle" in config.system_instruction


def test_chat_returns_502_when_cascade_is_exhausted(client, monkeypatch):
    fake_client = MagicMock()
    fake_client.generate.side_effect = RuntimeError(
        "Todos los modelos de la cascada agotaron su cuota"
    )
    monkeypatch.setattr(chat_module, "_client", fake_client)

    response = client.post("/chat/", json={"message": "Hola"})

    assert response.status_code == 502
    assert "ocupado" in response.json()["detail"]


def test_chat_returns_502_on_real_client_error(client, monkeypatch):
    fake_client = MagicMock()
    response_stub = MagicMock()
    response_stub.json.return_value = {
        "error": {"message": "bad request", "status": "INVALID_ARGUMENT"}
    }
    fake_client.generate.side_effect = ClientError(400, response_stub)
    monkeypatch.setattr(chat_module, "_client", fake_client)

    response = client.post("/chat/", json={"message": "Hola"})

    assert response.status_code == 502
    assert "ocupado" in response.json()["detail"]


def test_chat_returns_500_on_unexpected_error(client, monkeypatch):
    fake_client = MagicMock()
    fake_client.generate.side_effect = ValueError("algo inesperado")
    monkeypatch.setattr(chat_module, "_client", fake_client)

    response = client.post("/chat/", json={"message": "Hola"})

    assert response.status_code == 500
    assert response.json()["detail"] == "algo inesperado"


def test_chat_rejects_missing_message(client, monkeypatch):
    fake_client = MagicMock()
    monkeypatch.setattr(chat_module, "_client", fake_client)

    response = client.post("/chat/", json={})

    assert response.status_code == 422
    fake_client.generate.assert_not_called()
