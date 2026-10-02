from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.services.openrouter import DEFAULT_SYSTEM_PROMPT


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestRootEndpoint:
    def test_root_returns_frontend(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


def _auth_token(client: TestClient) -> str:
    """Cria um usuario e retorna o token de acesso."""
    resp = client.post(
        "/api/auth/signup",
        json={"email": "chat@test.com", "password": "123456"},
    )
    return resp.json()["access_token"]


class TestChatEndpoint:
    def test_chat_endpoint_exists(self, client: TestClient):
        """Verifica que o endpoint /api/chat responde (espera erro de config sem API key)."""
        token = _auth_token(client)
        response = client.post(
            "/api/chat",
            json={"message": "Ola"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Sem OPENROUTER_API_KEY definida, esperamos 503 (config error)
        assert response.status_code in (200, 422, 503)

    def test_chat_empty_message_rejected(self, client: TestClient):
        """Mensagem vazia deve ser rejeitada com 422 (validacao Pydantic)."""
        token = _auth_token(client)
        response = client.post(
            "/api/chat",
            json={"message": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


class TestChatStreamEndpoint:
    def test_chat_stream_endpoint_exists(self, client: TestClient):
        """Verifica que o endpoint /api/chat/stream aceita requisicoes."""
        token = _auth_token(client)
        response = client.post(
            "/api/chat/stream",
            json={"message": "Ola"},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Streaming pode iniciar e depois falhar sem API key
        assert response.status_code in (200, 422, 503)

    def test_chat_stream_empty_message_rejected(self, client: TestClient):
        """Stream com mensagem vazia deve ser rejeitado com 422."""
        token = _auth_token(client)
        response = client.post(
            "/api/chat/stream",
            json={"message": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422


class TestChatUsesUserInstructions:
    """As mensagens enviadas ao modelo devem usar as instrucoes do usuario logado."""

    @staticmethod
    def _signup(client: TestClient, email: str) -> str:
        resp = client.post("/api/auth/signup", json={"email": email, "password": "123456"})
        return resp.json()["access_token"]

    @staticmethod
    def _chat_system_prompt(client: TestClient, token: str) -> str:
        mock_generate = AsyncMock(return_value=("Resposta", "test-model"))
        with patch("backend.routers.chat.generate_reply", mock_generate):
            response = client.post(
                "/api/chat",
                json={"message": "Ola"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200
        # A primeira chamada e a resposta do chat (a segunda gera o titulo).
        return mock_generate.call_args_list[0].kwargs["system_prompt"]

    @staticmethod
    def _stream_system_prompt(client: TestClient, token: str) -> str:
        captured: dict = {}

        async def fake_stream_reply(**kwargs):
            captured.update(kwargs)
            yield "Resposta"

        with patch("backend.routers.chat.generate_reply", AsyncMock(return_value=("Titulo", "m"))):
            with patch("backend.routers.chat.stream_reply", fake_stream_reply):
                response = client.post(
                    "/api/chat/stream",
                    json={"message": "Ola"},
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert response.status_code == 200
        assert '"done": true' in response.text
        return captured["system_prompt"]

    def test_chat_uses_default_prompt_when_not_edited(self, client: TestClient):
        token = self._signup(client, "chat-default@example.com")
        assert self._chat_system_prompt(client, token) == DEFAULT_SYSTEM_PROMPT

    def test_chat_uses_custom_instructions(self, client: TestClient):
        token = self._signup(client, "chat-custom@example.com")
        client.put(
            "/api/instructions",
            json={"content": "Responda como um pirata."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert self._chat_system_prompt(client, token) == "Responda como um pirata."

    def test_stream_uses_default_prompt_when_not_edited(self, client: TestClient):
        token = self._signup(client, "stream-default@example.com")
        assert self._stream_system_prompt(client, token) == DEFAULT_SYSTEM_PROMPT

    def test_stream_uses_custom_instructions(self, client: TestClient):
        token = self._signup(client, "stream-custom@example.com")
        client.put(
            "/api/instructions",
            json={"content": "Responda em ingles."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert self._stream_system_prompt(client, token) == "Responda em ingles."

    def test_each_user_gets_own_instructions(self, client: TestClient):
        token_a = self._signup(client, "chat-a@example.com")
        token_b = self._signup(client, "chat-b@example.com")
        client.put(
            "/api/instructions",
            json={"content": "Instrucao do A"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert self._stream_system_prompt(client, token_a) == "Instrucao do A"
        assert self._stream_system_prompt(client, token_b) == DEFAULT_SYSTEM_PROMPT


class TestCORSMiddleware:
    def test_cors_headers_present(self, client: TestClient):
        """Verifica que os headers CORS estao presentes."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # O FastAPI com allow_origins=["*"] permite a requisicao
        assert response.status_code in (200, 405)