import os
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient
from hyperforge.harness_sdk import HarnessToolCall, ModelDelta

from team_partner.app import create_app
from team_partner.settings import EnvSettings


class ScopeModelClient:
    def __init__(self) -> None:
        self.calls = 0

    async def stream(self, **kwargs) -> AsyncIterator[ModelDelta]:
        self.calls += 1
        if self.calls == 1:
            yield ModelDelta(
                tool_calls=[
                    HarnessToolCall(
                        name="save_team_member",
                        arguments={"name": "Alex", "github_login": "alex"},
                    ),
                    HarnessToolCall(
                        name="save_jira_team",
                        arguments={
                            "board_id": 12,
                            "name": "Platform",
                            "project_key": "PLAT",
                        },
                    ),
                    HarnessToolCall(
                        name="save_github_repo",
                        arguments={"full_name": "example/platform"},
                    ),
                ]
            )
        elif self.calls == 2:
            yield ModelDelta(text="Saved the team's scope.")
        elif self.calls == 3:
            yield ModelDelta(tool_calls=[HarnessToolCall(name="get_team_context")])
        else:
            yield ModelDelta(text="Here is the team scope.")


def run_turn(client: TestClient, session_id: str, prompt: str) -> list[dict]:
    events = []
    with client.websocket_connect(f"/api/v1/agents/sessions/{session_id}/ws") as ws:
        for _ in range(4):
            ws.receive_json()
        ws.send_json({"command": "prompt", "prompt": prompt})
        while True:
            frame = ws.receive_json()
            if frame.get("object") == "agent.event":
                events.append(frame["event"])
                if frame["event"]["type"] == "turn.completed":
                    return events


def test_agent_manages_team_scope_across_restart(tmp_path):
    settings = EnvSettings(database_url=f"sqlite:///{tmp_path / 'team.db'}", _env_file=None)
    model = ScopeModelClient()
    with TestClient(create_app(settings, model_client=model)) as client:
        session_id = client.post("/api/v1/agents/sessions", json={}).json()["id"]
        events = run_turn(client, session_id, "Remember our team")
        completed = [e for e in events if e["type"] == "tool.completed"]
        assert {e["payload"]["tool"] for e in completed} == {
            "save_team_member",
            "save_jira_team",
            "save_github_repo",
        }

    with TestClient(create_app(settings, model_client=model)) as client:
        session_id = client.post("/api/v1/agents/sessions", json={}).json()["id"]
        events = run_turn(client, session_id, "What are we following?")
        scope = next(e["payload"]["result"] for e in events if e["type"] == "tool.completed")
        assert scope == {
            "members": [
                {
                    "name": "Alex",
                    "jira_account_id": None,
                    "github_login": "alex",
                    "ownership": None,
                }
            ],
            "jira_teams": [
                {
                    "board_id": 12,
                    "name": "Platform",
                    "project_key": "PLAT",
                    "site_url": None,
                }
            ],
            "github_repos": [{"full_name": "example/platform"}],
        }


class CLIModelClient:
    def __init__(self) -> None:
        self.calls = 0

    async def stream(self, **kwargs) -> AsyncIterator[ModelDelta]:
        self.calls += 1
        if self.calls == 1:
            yield ModelDelta(
                tool_calls=[
                    HarnessToolCall(
                        name="gh_cli",
                        arguments={"args": ["repo", "view", "example/platform; touch /tmp/should-not-run"]},
                    ),
                    HarnessToolCall(name="acli", arguments={"args": ["jira", "workitem", "list"]}),
                ]
            )
        else:
            yield ModelDelta(text="Commands finished.")


def test_agent_proxies_clis_with_literal_arguments(tmp_path, monkeypatch):
    for executable in ("gh", "acli"):
        script = tmp_path / executable
        script.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
        script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    settings = EnvSettings(database_url=f"sqlite:///{tmp_path / 'team.db'}", _env_file=None)
    with TestClient(create_app(settings, model_client=CLIModelClient())) as client:
        session_id = client.post("/api/v1/agents/sessions", json={}).json()["id"]
        events = run_turn(client, session_id, "Check the tools")
        results = {e["payload"]["tool"]: e["payload"]["result"] for e in events if e["type"] == "tool.completed"}
        assert results == {
            "gh_cli": {
                "exit_code": 0,
                "stdout": "repo\nview\nexample/platform; touch /tmp/should-not-run\n",
                "stderr": "",
            },
            "acli": {"exit_code": 0, "stdout": "jira\nworkitem\nlist\n", "stderr": ""},
        }
