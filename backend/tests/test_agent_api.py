from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from hyperforge.harness_sdk import ModelDelta

from team_partner.app import create_app
from team_partner.agents.tools import TeamsAlertResult
from team_partner.settings import EnvSettings


class StubModelClient:
    async def stream(self, **kwargs) -> AsyncIterator[ModelDelta]:
        yield ModelDelta(text="Let's identify the sprint blockers.")


def test_agent_conversation_survives_restart_without_identity(tmp_path):
    settings = EnvSettings(database_url=f"sqlite:///{tmp_path / 'team.db'}", _env_file=None)
    with TestClient(create_app(settings, model_client=StubModelClient())) as client:
        created = client.post("/api/v1/agents/sessions", json={})
        assert created.status_code == 201
        session_id = created.json()["id"]
        assert client.get("/api/v1/agents/sessions").json()[0]["id"] == session_id

        with client.websocket_connect(f"/api/v1/agents/sessions/{session_id}/ws") as ws:
            assert ws.receive_json()["object"] == "session"
            assert ws.receive_json()["object"] == "history.start"
            assert ws.receive_json()["object"] == "history.end"
            assert ws.receive_json()["object"] == "session.ready"
            ws.send_json({"command": "prompt", "prompt": "Help with our sprint"})
            while True:
                frame = ws.receive_json()
                if frame.get("event", {}).get("type") == "turn.completed":
                    assert "blockers" in frame["event"]["payload"]["text"]
                    break

        assert client.get(f"/api/v1/agents/sessions/{session_id}").status_code == 200

    with TestClient(create_app(settings, model_client=StubModelClient())) as client:
        events = client.get(f"/api/v1/agents/sessions/{session_id}/events").json()
        assert any(event["type"] == "turn.completed" for event in events)
        with client.websocket_connect(f"/api/v1/agents/sessions/{session_id}/ws") as ws:
            assert ws.receive_json()["object"] == "session"
            assert ws.receive_json()["object"] == "history.start"
            assert ws.receive_json()["replay"] is True
        assert client.delete(f"/api/v1/agents/sessions/{session_id}").status_code == 204
        assert client.get(f"/api/v1/agents/sessions/{session_id}").status_code == 404


def test_notify_endpoint_sends_teams_alert(tmp_path, monkeypatch):
    import team_partner.app as app_module

    async def fake_post_teams_webhook(
        url: str, message: str, title: str | None = None, bearer_token: str | None = None
    ) -> TeamsAlertResult:
        assert url == "https://example.invalid/webhook"
        assert title == "Execution Partner Alert"
        assert "High priority" in message
        return TeamsAlertResult(delivered=True, status_code=200, message="Alert sent to Teams")

    monkeypatch.setattr(app_module, "post_teams_webhook", fake_post_teams_webhook)

    settings = EnvSettings(
        database_url=f"sqlite:///{tmp_path / 'team.db'}",
        teams_webhook_url="https://example.invalid/webhook",
        _env_file=None,
    )
    with TestClient(create_app(settings, model_client=StubModelClient())) as client:
        response = client.post("/api/v1/alerts/notify", json={})
        assert response.status_code == 200
        assert response.json() == {
            "delivered": True,
            "status_code": 200,
            "message": "Alert sent to Teams",
        }


def test_notify_endpoint_requires_webhook(tmp_path):
    settings = EnvSettings(database_url=f"sqlite:///{tmp_path / 'team.db'}", _env_file=None)
    with TestClient(create_app(settings, model_client=StubModelClient())) as client:
        response = client.post("/api/v1/alerts/notify", json={})
        assert response.status_code == 400
        assert response.json()["detail"] == "No Teams webhook configured. Set TEAMS_WEBHOOK_URL or provide webhook_url."
