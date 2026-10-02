from __future__ import annotations

from fastapi.testclient import TestClient

from backend.services.openrouter import DEFAULT_SYSTEM_PROMPT


def _signup(client: TestClient, email: str, password: str = "123456") -> str:
    resp = client.post("/api/auth/signup", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestInstructionsAuth:
    def test_get_requires_auth(self, client: TestClient):
        assert client.get("/api/instructions").status_code == 401

    def test_put_requires_auth(self, client: TestClient):
        response = client.put("/api/instructions", json={"content": "Oi"})
        assert response.status_code == 401

    def test_delete_requires_auth(self, client: TestClient):
        assert client.delete("/api/instructions").status_code == 401


class TestInstructionsDefault:
    def test_new_user_gets_default_prompt(self, client: TestClient):
        token = _signup(client, "default@example.com")
        response = client.get("/api/instructions", headers=_auth(token))
        assert response.status_code == 200
        data = response.json()
        assert data["is_default"] is True
        assert data["content"] == DEFAULT_SYSTEM_PROMPT
        assert data["default_content"] == DEFAULT_SYSTEM_PROMPT


class TestInstructionsUpdate:
    def test_update_and_read_back(self, client: TestClient):
        token = _signup(client, "update@example.com")
        response = client.put(
            "/api/instructions",
            json={"content": "  Responda sempre em ingles.  "},
            headers=_auth(token),
        )
        assert response.status_code == 200
        assert response.json() == {
            "content": "Responda sempre em ingles.",
            "is_default": False,
            "default_content": DEFAULT_SYSTEM_PROMPT,
        }

        data = client.get("/api/instructions", headers=_auth(token)).json()
        assert data["content"] == "Responda sempre em ingles."
        assert data["is_default"] is False

    def test_update_twice_overwrites(self, client: TestClient):
        token = _signup(client, "twice@example.com")
        client.put("/api/instructions", json={"content": "Primeira"}, headers=_auth(token))
        client.put("/api/instructions", json={"content": "Segunda"}, headers=_auth(token))
        data = client.get("/api/instructions", headers=_auth(token)).json()
        assert data["content"] == "Segunda"

    def test_empty_content_restores_default(self, client: TestClient):
        token = _signup(client, "empty@example.com")
        client.put("/api/instructions", json={"content": "Algo"}, headers=_auth(token))
        response = client.put("/api/instructions", json={"content": "   "}, headers=_auth(token))
        assert response.status_code == 200
        assert response.json()["is_default"] is True
        assert response.json()["content"] == DEFAULT_SYSTEM_PROMPT

    def test_delete_restores_default(self, client: TestClient):
        token = _signup(client, "reset@example.com")
        client.put("/api/instructions", json={"content": "Algo"}, headers=_auth(token))
        response = client.delete("/api/instructions", headers=_auth(token))
        assert response.status_code == 200
        assert response.json()["is_default"] is True
        data = client.get("/api/instructions", headers=_auth(token)).json()
        assert data["content"] == DEFAULT_SYSTEM_PROMPT

    def test_content_too_long_rejected(self, client: TestClient):
        token = _signup(client, "long@example.com")
        response = client.put(
            "/api/instructions", json={"content": "x" * 4001}, headers=_auth(token)
        )
        assert response.status_code == 422


class TestInstructionsIsolation:
    def test_users_do_not_see_each_other(self, client: TestClient):
        token_a = _signup(client, "alice@example.com")
        token_b = _signup(client, "bob@example.com")

        client.put("/api/instructions", json={"content": "Instrucao da Alice"}, headers=_auth(token_a))

        data_b = client.get("/api/instructions", headers=_auth(token_b)).json()
        assert data_b["is_default"] is True
        assert data_b["content"] == DEFAULT_SYSTEM_PROMPT

    def test_user_cannot_change_other_user(self, client: TestClient):
        token_a = _signup(client, "carol@example.com")
        token_b = _signup(client, "dave@example.com")

        client.put("/api/instructions", json={"content": "Instrucao da Carol"}, headers=_auth(token_a))
        client.put("/api/instructions", json={"content": "Instrucao do Dave"}, headers=_auth(token_b))
        client.delete("/api/instructions", headers=_auth(token_b))

        data_a = client.get("/api/instructions", headers=_auth(token_a)).json()
        assert data_a["content"] == "Instrucao da Carol"


class TestInstructionsPersistence:
    def test_survives_logout_and_login(self, client: TestClient):
        token = _signup(client, "persist@example.com", "senha123")
        client.put("/api/instructions", json={"content": "Seja formal."}, headers=_auth(token))

        client.post("/api/auth/logout", headers=_auth(token))
        assert client.get("/api/instructions", headers=_auth(token)).status_code == 401

        login = client.post(
            "/api/auth/login", json={"email": "persist@example.com", "password": "senha123"}
        )
        new_token = login.json()["access_token"]

        data = client.get("/api/instructions", headers=_auth(new_token)).json()
        assert data["content"] == "Seja formal."
        assert data["is_default"] is False