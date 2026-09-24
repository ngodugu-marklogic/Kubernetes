import asyncio
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from hyperforge.harness_sdk import HarnessTool, ToolCallContext
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from team_partner.agents.team_context import (
    GitHubRepo,
    JiraTeam,
    TeamContext,
    TeamContextStorage,
    TeamMember,
    TeamsChannel,
)
from team_partner.settings import EnvSettings


class RemoveMember(BaseModel):
    name: str


class RemoveJiraTeam(BaseModel):
    board_id: int


class RemoveGitHubRepo(BaseModel):
    full_name: str


class RemoveTeamsChannel(BaseModel):
    channel_id: str


class Removed(BaseModel):
    removed: bool


class CLICommand(BaseModel):
    args: list[str] = Field(
        min_length=1,
        description="Arguments after the CLI executable, as separate strings",
    )


class CLIResult(BaseModel):
    exit_code: int | None
    stdout: str
    stderr: str


class TeamsAlert(BaseModel):
    message: str = Field(min_length=1)
    title: str | None = None
    webhook_url: str | None = None


class TeamsAlertResult(BaseModel):
    delivered: bool
    status_code: int | None = None
    message: str


class EmptyInput(BaseModel):
    pass


async def run_cli(executable: str, args: list[str]) -> CLIResult:
    """Use the host's existing CLI authentication without invoking a shell."""
    try:
        process = await asyncio.create_subprocess_exec(
            executable,
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return CLIResult(
            exit_code=None,
            stdout="",
            stderr=f"{executable} is not installed or not on PATH",
        )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
    except TimeoutError:
        process.kill()
        await process.communicate()
        return CLIResult(exit_code=None, stdout="", stderr=f"{executable} timed out after 30 seconds")
    except asyncio.CancelledError:
        process.kill()
        await process.communicate()
        raise
    return CLIResult(
        exit_code=process.returncode,
        stdout=stdout[:16000].decode(errors="replace"),
        stderr=stderr[:16000].decode(errors="replace"),
    )


async def post_teams_webhook(url: str, message: str, title: str | None = None) -> TeamsAlertResult:
    payload = {"text": f"**{title}**\n\n{message}" if title else message}
    body = json.dumps(payload).encode("utf-8")

    def send_request() -> TeamsAlertResult:
        request = Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=10) as response:
                status = getattr(response, "status", None)
                return TeamsAlertResult(delivered=True, status_code=status, message="Alert sent to Teams")
        except HTTPError as exc:
            return TeamsAlertResult(delivered=False, status_code=exc.code, message=f"Teams webhook returned HTTP {exc.code}")
        except URLError as exc:
            return TeamsAlertResult(delivered=False, status_code=None, message=f"Teams webhook failed: {exc.reason}")

    return await asyncio.to_thread(send_request)


def create_team_tools(factory: sessionmaker[Session], settings: EnvSettings) -> tuple[HarnessTool, ...]:
    storage = TeamContextStorage(factory)

    async def get_team_context(context: ToolCallContext, input_value: EmptyInput) -> TeamContext:
        return storage.get()

    async def save_team_member(context: ToolCallContext, input_value: TeamMember) -> TeamMember:
        return storage.save_member(input_value)

    async def remove_team_member(context: ToolCallContext, input_value: RemoveMember) -> Removed:
        return Removed(removed=storage.remove_member(input_value.name))

    async def save_jira_team(context: ToolCallContext, input_value: JiraTeam) -> JiraTeam:
        return storage.save_jira_team(input_value)

    async def remove_jira_team(context: ToolCallContext, input_value: RemoveJiraTeam) -> Removed:
        return Removed(removed=storage.remove_jira_team(input_value.board_id))

    async def save_github_repo(context: ToolCallContext, input_value: GitHubRepo) -> GitHubRepo:
        return storage.save_github_repo(input_value)

    async def remove_github_repo(context: ToolCallContext, input_value: RemoveGitHubRepo) -> Removed:
        return Removed(removed=storage.remove_github_repo(input_value.full_name))

    async def save_teams_channel(context: ToolCallContext, input_value: TeamsChannel) -> TeamsChannel:
        return storage.save_teams_channel(input_value)

    async def remove_teams_channel(context: ToolCallContext, input_value: RemoveTeamsChannel) -> Removed:
        return Removed(removed=storage.remove_teams_channel(input_value.channel_id))

    async def gh_cli(context: ToolCallContext, input_value: CLICommand) -> CLIResult:
        return await run_cli("gh", input_value.args)

    async def acli(context: ToolCallContext, input_value: CLICommand) -> CLIResult:
        return await run_cli("acli", input_value.args)

    async def teams_send_alert(context: ToolCallContext, input_value: TeamsAlert) -> TeamsAlertResult:
        webhook_url = input_value.webhook_url or settings.teams_webhook_url
        if not webhook_url:
            return TeamsAlertResult(
                delivered=False,
                status_code=None,
                message="No Teams webhook URL configured. Set TEAMS_WEBHOOK_URL or provide webhook_url in the tool call.",
            )
        return await post_teams_webhook(webhook_url, input_value.message, input_value.title)

    return (
        HarnessTool(
            "get_team_context",
            get_team_context,
            "Read the team's saved members, Jira boards, GitHub repositories, and Teams channels.",
        ),
        HarnessTool(
            "save_team_member",
            save_team_member,
            "Add or update a team member by name, with optional Jira account ID, GitHub login and ownership.",
        ),
        HarnessTool("remove_team_member", remove_team_member, "Remove a team member by name."),
        HarnessTool(
            "save_jira_team",
            save_jira_team,
            "Add or update a Jira agile board to follow, identified by board ID; optionally save project key and site URL.",
        ),
        HarnessTool(
            "remove_jira_team",
            remove_jira_team,
            "Stop following a Jira agile board by board ID.",
        ),
        HarnessTool(
            "save_github_repo",
            save_github_repo,
            "Add a GitHub repository to follow, in owner/repo format.",
        ),
        HarnessTool(
            "remove_github_repo",
            remove_github_repo,
            "Stop following a GitHub repository by owner/repo.",
        ),
        HarnessTool(
            "save_teams_channel",
            save_teams_channel,
            "Add or update a Microsoft Teams channel to follow, including optional incoming webhook URL for alerts.",
        ),
        HarnessTool(
            "remove_teams_channel",
            remove_teams_channel,
            "Stop following a Microsoft Teams channel by channel_id.",
        ),
        HarnessTool(
            "gh_cli",
            gh_cli,
            "Run the machine's authenticated gh CLI. Supply argv as separate strings; use saved repositories to scope queries. Results include exit code and output.",
        ),
        HarnessTool(
            "acli",
            acli,
            "Run the machine's authenticated acli Jira/Confluence CLI. Supply argv as separate strings; use saved Jira boards to scope queries. Results include exit code and output.",
        ),
        HarnessTool(
            "teams_send_alert",
            teams_send_alert,
            "Send an alert message to Microsoft Teams using an incoming webhook URL.",
        ),
    )
