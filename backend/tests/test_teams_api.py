from fastapi.testclient import TestClient

from team_partner.app import create_app
from team_partner.settings import EnvSettings


def test_list_teams_uses_injected_provider(tmp_path):
    settings = EnvSettings(database_url=f"sqlite:///{tmp_path / 'team.db'}", _env_file=None)
    with TestClient(create_app(settings, team_provider=lambda: ["Platform", "Growth"])) as client:
        response = client.get("/api/v1/teams")
        assert response.status_code == 200
        assert response.json() == {"teams": ["Platform", "Growth"]}


def test_list_teams_defaults_to_placeholder_provider(tmp_path):
    settings = EnvSettings(database_url=f"sqlite:///{tmp_path / 'team.db'}", _env_file=None)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/teams")
        assert response.status_code == 200
        assert response.json()["teams"]
