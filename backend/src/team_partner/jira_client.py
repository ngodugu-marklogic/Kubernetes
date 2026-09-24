"""Temporary direct Jira REST access for teams/stories, until the Jira MCP integration lands.

Discovers the "Agile Team" custom field by name, then queries issues with that field set to
build the team list and per-team story list. Any failure falls back to the existing placeholders.
"""

import logging
import time
from datetime import datetime, timezone

import httpx

from team_partner.settings import EnvSettings
from team_partner.stories import Story, StoryProvider, placeholder_story_provider
from team_partner.teams import TeamProvider, placeholder_team_provider

logger = logging.getLogger(__name__)

AGILE_TEAM_FIELD_NAME = "Agile Team"
# Live queries scan hundreds of issues and take several seconds; cache results briefly
# so page loads don't re-scan Jira on every request.
CACHE_TTL_SECONDS = 60
# Keep in sync with HIDDEN_STATUSES in src/TeamsLanding.tsx: excluded here so the paginated
# fetch spends its result budget on active work instead of finished issues.
FINISHED_STATUSES = ["Done", "Ready To Ship", "Shipped"]


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            auth=(email, api_token),
            headers={"Accept": "application/json"},
            timeout=15,
        )
        self._field_id: str | None = None
        self._teams_cache: tuple[float, list[str]] | None = None
        self._stories_cache: dict[str, tuple[float, list[Story]]] = {}

    def _agile_team_field_id(self) -> str | None:
        if self._field_id is not None:
            return self._field_id
        response = self._client.get("/rest/api/3/field")
        response.raise_for_status()
        for field in response.json():
            if str(field.get("name", "")).strip().lower() == AGILE_TEAM_FIELD_NAME.lower():
                self._field_id = field["id"]
                return self._field_id
        logger.warning("Jira field %r not found on %s", AGILE_TEAM_FIELD_NAME, self._client.base_url)
        return None

    def fetch_teams(self) -> list[str]:
        if self._teams_cache is not None:
            cached_at, teams = self._teams_cache
            if time.monotonic() - cached_at < CACHE_TTL_SECONDS:
                return teams
        field_id = self._agile_team_field_id()
        if field_id is None:
            return []
        jql = f"cf[{field_id.removeprefix('customfield_')}] is not EMPTY"
        teams: set[str] = set()
        next_page_token: str | None = None
        for _ in range(20):  # safety cap: up to ~2000 issues
            body = {"jql": jql, "fields": [field_id], "maxResults": 100}
            if next_page_token:
                body["nextPageToken"] = next_page_token
            response = self._client.post("/rest/api/3/search/jql", json=body)
            response.raise_for_status()
            page = response.json()
            for issue in page.get("issues", []):
                value = _extract_value(issue.get("fields", {}).get(field_id))
                if value:
                    teams.add(value)
            next_page_token = page.get("nextPageToken")
            if not next_page_token:
                break
        result = sorted(teams)
        self._teams_cache = (time.monotonic(), result)
        return result

    def fetch_stories(self, team: str) -> list[Story]:
        if team in self._stories_cache:
            cached_at, stories = self._stories_cache[team]
            if time.monotonic() - cached_at < CACHE_TTL_SECONDS:
                return stories
        field_id = self._agile_team_field_id()
        if field_id is None:
            return []
        escaped_team = team.replace('"', '\\"')
        excluded_statuses = ", ".join(f'"{status}"' for status in FINISHED_STATUSES)
        jql = (
            f'cf[{field_id.removeprefix("customfield_")}] = "{escaped_team}" '
            f"AND status not in ({excluded_statuses}) ORDER BY updated DESC"
        )
        stories: list[Story] = []
        next_page_token: str | None = None
        for _ in range(5):  # safety cap: up to 500 issues
            body = {
                "jql": jql,
                "fields": ["summary", "status", "assignee", "updated"],
                "maxResults": 100,
            }
            if next_page_token:
                body["nextPageToken"] = next_page_token
            response = self._client.post("/rest/api/3/search/jql", json=body)
            response.raise_for_status()
            page = response.json()
            stories.extend(_to_story(issue) for issue in page.get("issues", []))
            next_page_token = page.get("nextPageToken")
            if not next_page_token:
                break
        self._stories_cache[team] = (time.monotonic(), stories)
        return stories

    def close(self) -> None:
        self._client.close()


def _extract_value(raw: object) -> str | None:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        for key in ("value", "name", "title", "displayName"):
            found = raw.get(key)
            if isinstance(found, str):
                return found
        return None
    if isinstance(raw, list):
        for item in raw:
            value = _extract_value(item)
            if value:
                return value
    return None


def _to_story(issue: dict) -> Story:
    fields = issue.get("fields", {})
    assignee = fields.get("assignee") or {}
    return Story(
        key=issue["key"],
        summary=fields.get("summary", ""),
        status=(fields.get("status") or {}).get("name", "Unknown"),
        assignee=assignee.get("displayName"),
        last_activity=_relative_update(fields.get("updated")),
    )


def _relative_update(updated: str | None) -> str | None:
    if not updated:
        return None
    try:
        when = datetime.fromisoformat(updated)
    except ValueError:
        return None
    hours = int((datetime.now(timezone.utc) - when.astimezone(timezone.utc)).total_seconds() // 3600)
    if hours < 1:
        return "Updated less than an hour ago"
    if hours < 24:
        return f"Updated {hours}h ago"
    return f"Updated {hours // 24}d ago"


def build_live_providers(settings: EnvSettings) -> tuple[TeamProvider, StoryProvider] | None:
    """Live Jira-backed providers, or None if Jira credentials aren't configured."""
    if not (settings.jira_base_url and settings.jira_email and settings.jira_api_token):
        return None
    client = JiraClient(settings.jira_base_url, settings.jira_email, settings.jira_api_token)

    def team_provider() -> list[str]:
        try:
            return client.fetch_teams() or placeholder_team_provider()
        except httpx.HTTPError:
            logger.exception("Live Jira team query failed; falling back to placeholder teams")
            return placeholder_team_provider()

    def story_provider(team: str) -> list[Story]:
        try:
            return client.fetch_stories(team) or placeholder_story_provider(team)
        except httpx.HTTPError:
            logger.exception("Live Jira story query failed; falling back to placeholder stories")
            return placeholder_story_provider(team)

    return team_provider, story_provider
