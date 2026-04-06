from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from ipilot.api.server import app


def test_health_endpoint():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_completions_uses_ipilot(monkeypatch):
    class FakeBot:
        async def run(self, message: str, session_key: str, channel=None, chat_id=None):
            return SimpleNamespace(content=f"echo:{message}", finish_reason="stop")

    monkeypatch.setattr("ipilot.api.server.iPilot.from_config", lambda: FakeBot())

    client = TestClient(app)
    response = client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "echo:hello"

