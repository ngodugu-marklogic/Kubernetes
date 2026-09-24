from fastapi.testclient import TestClient

from team_partner.app import create_app
from team_partner.settings import EnvSettings
from team_partner.stories import Story


def test_list_team_stories_uses_injected_provider(tmp_path):
    settings = EnvSettings(database_url=f"sqlite:///{tmp_path / 'team.db'}", _env_file=None)
    provider = lambda team: [Story(key="EX-1", summary=f"{team} work", status="To Do")]
    with TestClient(create_app(settings, story_provider=provider)) as client:
        response = client.get("/api/v1/teams/Platform/stories")
        assert response.status_code == 200
        assert response.json() == {
            "stories": [
                {
                    "key": "EX-1",
                    "summary": "Platform work",
                    "status": "To Do",
                    "assignee": None,
                    "last_activity": None,
                    "branches": [],
                    "pull_requests": [],
                }
            ]
        }


def test_list_team_stories_defaults_to_placeholder_provider(tmp_path):
    settings = EnvSettings(database_url=f"sqlite:///{tmp_path / 'team.db'}", _env_file=None)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/teams/Platform/stories")
        assert response.status_code == 200
        assert response.json()["stories"]
