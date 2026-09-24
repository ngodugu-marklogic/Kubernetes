import uvicorn

from team_partner.settings import env_settings


def run_api() -> None:
    uvicorn.run(
        "team_partner.app:app",
        host=env_settings.http_host,
        port=env_settings.http_port,
        reload=env_settings.debug,
    )
