from collections.abc import Callable

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


class PullRequest(BaseModel):
    title: str
    url: str
    status: str


class Story(BaseModel):
    key: str
    summary: str
    status: str
    assignee: str | None = None
    last_activity: str | None = None
    branches: list[str] = Field(default_factory=list)
    pull_requests: list[PullRequest] = Field(default_factory=list)


StoryProvider = Callable[[str], list[Story]]


class StoriesResponse(BaseModel):
    stories: list[Story]


def placeholder_story_provider(team: str) -> list[Story]:
    """Stand-in until the Jira MCP integration supplies real stories for the Agile Team field."""
    return [
        Story(
            key="EX-101",
            summary=f"Investigate {team} onboarding gaps",
            status="In Progress",
            assignee="Jamie Lee",
            last_activity="Jamie Lee changed status from To Do to In Progress 2 hours ago",
            branches=["feature/ex-101-onboarding-gaps"],
            pull_requests=[
                PullRequest(title="Add onboarding gap analysis", url="https://github.com/example/repo/pull/101", status="Open")
            ],
        ),
        Story(
            key="EX-102",
            summary=f"Reduce {team} review cycle time",
            status="To Do",
            assignee=None,
            last_activity="Comment added by Morgan Diaz yesterday",
            branches=[],
            pull_requests=[],
        ),
        Story(
            key="EX-103",
            summary=f"Ship {team} dashboard beta",
            status="Done",
            assignee="Morgan Diaz",
            last_activity="Morgan Diaz resolved this issue 3 days ago",
            branches=["feature/ex-103-dashboard-beta"],
            pull_requests=[
                PullRequest(title="Dashboard beta rollout", url="https://github.com/example/repo/pull/103", status="Merged")
            ],
        ),
    ]


@router.get("/{team}/stories", response_model=StoriesResponse)
async def list_team_stories(team: str, request: Request) -> StoriesResponse:
    provider: StoryProvider = request.app.state.story_provider
    return StoriesResponse(stories=provider(team))
