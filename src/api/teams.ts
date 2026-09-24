const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8888';

export async function fetchTeams(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/teams`);
  if (!response.ok) {
    throw new Error(`Failed to load teams: ${response.status}`);
  }
  const data: { teams: string[] } = await response.json();
  return data.teams;
}

export interface PullRequest {
  title: string;
  url: string;
  status: string;
}

export interface Story {
  key: string;
  summary: string;
  status: string;
  assignee: string | null;
  last_activity: string | null;
  branches: string[];
  pull_requests: PullRequest[];
}

export async function fetchTeamStories(team: string): Promise<Story[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/teams/${encodeURIComponent(team)}/stories`);
  if (!response.ok) {
    throw new Error(`Failed to load stories: ${response.status}`);
  }
  const data: { stories: Story[] } = await response.json();
  return data.stories;
}
