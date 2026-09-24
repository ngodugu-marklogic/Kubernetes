from collections.abc import Callable

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])

TeamProvider = Callable[[], list[str]]


class TeamsResponse(BaseModel):
    teams: list[str]


def placeholder_team_provider() -> list[str]:
    """Stand-in until the Jira MCP integration supplies real "Agile Team" field values."""
    return ["Team Alpha", "Team Bravo", "Team Charlie"]


@router.get("", response_model=TeamsResponse)
async def list_teams(request: Request) -> TeamsResponse:
    provider: TeamProvider = request.app.state.team_provider
    return TeamsResponse(teams=provider())
