const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8888';

export async function fetchTeams(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/teams`);
  if (!response.ok) {
    throw new Error(`Failed to load teams: ${response.status}`);
  }
  const data: { teams: string[] } = await response.json();
  return data.teams;
}
