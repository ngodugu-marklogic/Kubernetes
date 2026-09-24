from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from team_partner.db import GitHubRepoRow, JiraTeamRow, TeamMemberRow, TeamsChannelRow, transaction


class TeamMember(BaseModel):
    name: str = Field(min_length=1)
    jira_account_id: str | None = None
    github_login: str | None = None
    ownership: str | None = None


class JiraTeam(BaseModel):
    board_id: int = Field(gt=0)
    name: str = Field(min_length=1)
    project_key: str | None = None
    site_url: str | None = None


class GitHubRepo(BaseModel):
    full_name: str = Field(pattern=r"^[^/\s]+/[^/\s]+$")


class TeamsChannel(BaseModel):
    channel_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    webhook_url: str | None = None


class TeamContext(BaseModel):
    members: list[TeamMember]
    jira_teams: list[JiraTeam]
    github_repos: list[GitHubRepo]
    teams_channels: list[TeamsChannel]


class TeamContextStorage:
    """Shared, structured scope for all conversations in this backend."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self.factory = factory

    def get(self) -> TeamContext:
        with self.factory() as session:
            return TeamContext(
                members=[
                    TeamMember.model_validate(row, from_attributes=True)
                    for row in session.scalars(select(TeamMemberRow).order_by(TeamMemberRow.name))
                ],
                jira_teams=[
                    JiraTeam.model_validate(row, from_attributes=True)
                    for row in session.scalars(select(JiraTeamRow).order_by(JiraTeamRow.board_id))
                ],
                github_repos=[
                    GitHubRepo.model_validate(row, from_attributes=True)
                    for row in session.scalars(select(GitHubRepoRow).order_by(GitHubRepoRow.full_name))
                ],
                teams_channels=[
                    TeamsChannel.model_validate(row, from_attributes=True)
                    for row in session.scalars(select(TeamsChannelRow).order_by(TeamsChannelRow.channel_id))
                ],
            )

    def save_member(self, member: TeamMember) -> TeamMember:
        with transaction(self.factory) as session:
            row = session.get(TeamMemberRow, member.name)
            if row is None:
                row = TeamMemberRow(**member.model_dump())
                session.add(row)
            else:
                for field in member.model_fields_set - {"name"}:
                    setattr(row, field, getattr(member, field))
            return TeamMember.model_validate(row, from_attributes=True)

    def remove_member(self, name: str) -> bool:
        with transaction(self.factory) as session:
            row = session.get(TeamMemberRow, name)
            if row is None:
                return False
            session.delete(row)
        return True

    def save_jira_team(self, team: JiraTeam) -> JiraTeam:
        with transaction(self.factory) as session:
            row = session.get(JiraTeamRow, team.board_id)
            if row is None:
                row = JiraTeamRow(**team.model_dump())
                session.add(row)
            else:
                for field in team.model_fields_set - {"board_id"}:
                    setattr(row, field, getattr(team, field))
            return JiraTeam.model_validate(row, from_attributes=True)

    def remove_jira_team(self, board_id: int) -> bool:
        with transaction(self.factory) as session:
            row = session.get(JiraTeamRow, board_id)
            if row is None:
                return False
            session.delete(row)
        return True

    def save_github_repo(self, repo: GitHubRepo) -> GitHubRepo:
        with transaction(self.factory) as session:
            session.merge(GitHubRepoRow(**repo.model_dump()))
        return repo

    def remove_github_repo(self, full_name: str) -> bool:
        with transaction(self.factory) as session:
            row = session.get(GitHubRepoRow, full_name)
            if row is None:
                return False
            session.delete(row)
        return True

    def save_teams_channel(self, channel: TeamsChannel) -> TeamsChannel:
        with transaction(self.factory) as session:
            row = session.get(TeamsChannelRow, channel.channel_id)
            if row is None:
                row = TeamsChannelRow(**channel.model_dump())
                session.add(row)
            else:
                for field in channel.model_fields_set - {"channel_id"}:
                    setattr(row, field, getattr(channel, field))
            return TeamsChannel.model_validate(row, from_attributes=True)

    def remove_teams_channel(self, channel_id: str) -> bool:
        with transaction(self.factory) as session:
            row = session.get(TeamsChannelRow, channel_id)
            if row is None:
                return False
            session.delete(row)
        return True
