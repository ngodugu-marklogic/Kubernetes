import { useEffect, useState } from 'react';

import { fetchTeams, fetchTeamStories, type Story } from '@/api/teams';

type LoadState = 'loading' | 'ready';

// Jira's workflow progression, used to order the story list (unlisted statuses sort just before "Under Consideration").
const STATUS_ORDER = ['Ready For PO Review', 'In Development', 'In Progress', 'To Do', 'Backlog', 'Under Consideration'];
const UNKNOWN_STATUS_RANK = STATUS_ORDER.length - 1;

const statusRank = (status: string): number => {
  const index = STATUS_ORDER.findIndex((candidate) => candidate.toLowerCase() === status.toLowerCase());
  return index === -1 ? UNKNOWN_STATUS_RANK : index;
};

// Shown until the Jira integration is connected and the API has real "Agile Team" data.
const FALLBACK_TEAMS = ['Team Alpha', 'Team Bravo', 'Team Charlie'];

// Shown until the Jira integration is connected and the API has real stories for a team.
const fallbackStories = (team: string): Story[] => [
  {
    key: 'EX-101',
    summary: `Investigate ${team} onboarding gaps`,
    status: 'In Progress',
    assignee: 'Jamie Lee',
    last_activity: 'Jamie Lee changed status from To Do to In Progress 2 hours ago',
    branches: ['feature/ex-101-onboarding-gaps'],
    pull_requests: [
      { title: 'Add onboarding gap analysis', url: 'https://github.com/example/repo/pull/101', status: 'Open' },
    ],
  },
  {
    key: 'EX-102',
    summary: `Reduce ${team} review cycle time`,
    status: 'To Do',
    assignee: null,
    last_activity: 'Comment added by Morgan Diaz yesterday',
    branches: [],
    pull_requests: [],
  },
  {
    key: 'EX-103',
    summary: `Ship ${team} dashboard beta`,
    status: 'Done',
    assignee: 'Morgan Diaz',
    last_activity: 'Morgan Diaz resolved this issue 3 days ago',
    branches: ['feature/ex-103-dashboard-beta'],
    pull_requests: [
      { title: 'Dashboard beta rollout', url: 'https://github.com/example/repo/pull/103', status: 'Merged' },
    ],
  },
];

// Statuses that represent finished work and shouldn't clutter the active story list.
const HIDDEN_STATUSES = new Set(['done', 'ready to ship', 'shipped']);

const priorities = [
  { title: 'Review launch criteria', owner: 'You', status: 'In progress' },
  { title: 'Resolve API dependency', owner: 'Platform', status: 'Blocked' },
  { title: 'Prepare stakeholder update', owner: 'You', status: 'Ready' },
];

export const TeamsLanding = () => {
  const [teams, setTeams] = useState<string[]>([]);
  const [state, setState] = useState<LoadState>('loading');
  const [usingFallback, setUsingFallback] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [stories, setStories] = useState<Story[]>([]);
  const [storiesTeam, setStoriesTeam] = useState<string | null>(null);
  const [storiesUsingFallback, setStoriesUsingFallback] = useState(false);
  const [storiesCollapsed, setStoriesCollapsed] = useState(false);
  const storiesState: LoadState = selectedTeam !== null && storiesTeam !== selectedTeam ? 'loading' : 'ready';

  useEffect(() => {
    let cancelled = false;

    fetchTeams()
      .then((result) => {
        if (cancelled) return;
        setTeams(result);
        setState('ready');
        setSelectedTeam((current) => current ?? result[0] ?? null);
      })
      .catch(() => {
        if (cancelled) return;
        setTeams(FALLBACK_TEAMS);
        setUsingFallback(true);
        setState('ready');
        setSelectedTeam((current) => current ?? FALLBACK_TEAMS[0] ?? null);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedTeam) return;
    let cancelled = false;

    fetchTeamStories(selectedTeam)
      .then((result) => {
        if (cancelled) return;
        setStories(result);
        setStoriesUsingFallback(false);
        setStoriesTeam(selectedTeam);
      })
      .catch(() => {
        if (cancelled) return;
        setStories(fallbackStories(selectedTeam));
        setStoriesUsingFallback(true);
        setStoriesTeam(selectedTeam);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedTeam]);

  const sortedStories = stories
    .filter((story) => !HIDDEN_STATUSES.has(story.status.toLowerCase()))
    .sort((a, b) => statusRank(a.status) - statusRank(b.status) || (a.assignee ?? 'Unassigned').localeCompare(b.assignee ?? 'Unassigned'));

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1>Execution Partner</h1>
        </div>
      </header>

      <div className="teams-layout">
        <nav className="team-sidebar" aria-labelledby="teams-heading">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Get started</p>
              <h2 id="teams-heading">Choose a team</h2>
            </div>
          </div>

          {usingFallback && (
            <p className="team-picker-status team-picker-status-notice">
              Showing placeholder teams until Jira is connected.
            </p>
          )}
          {state === 'loading' && <p className="team-picker-status">Loading teams…</p>}
          {state === 'ready' && teams.length === 0 && (
            <p className="team-picker-status">No teams found yet.</p>
          )}
          {state === 'ready' && teams.length > 0 && (
            <ul className="team-list">
              {teams.map((team) => (
                <li key={team}>
                  <button
                    type="button"
                    className={`team-option${team === selectedTeam ? ' team-option-selected' : ''}`}
                    aria-pressed={team === selectedTeam}
                    onClick={() => setSelectedTeam(team)}
                  >
                    {team}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </nav>

        <section className="team-detail" aria-labelledby="team-detail-heading">
          {selectedTeam ? (
            <>
              <div className="section-heading">
                <div>
                  <p className="eyebrow">Team</p>
                  <h2 id="team-detail-heading">{selectedTeam}</h2>
                </div>
                <button type="button" className="primary-action">
                  Add priority
                </button>
              </div>

              <div className="team-detail-body">
                <section className="worklist" aria-labelledby="stories-heading">
                  <div className="section-heading">
                    <div className="heading-with-toggle">
                      <button
                        type="button"
                        className={`collapse-toggle${storiesCollapsed ? ' collapse-toggle-collapsed' : ''}`}
                        aria-expanded={!storiesCollapsed}
                        aria-label={storiesCollapsed ? 'Expand stories' : 'Collapse stories'}
                        onClick={() => setStoriesCollapsed((collapsed) => !collapsed)}
                      >
                        <span aria-hidden="true" className="collapse-toggle-arrow">
                          ▾
                        </span>
                      </button>
                      <div>
                        <p className="eyebrow">Jira</p>
                        <h2 id="stories-heading">Stories</h2>
                      </div>
                    </div>
                  </div>

                  {!storiesCollapsed && (
                    <>
                      {storiesUsingFallback && (
                        <p className="team-picker-status team-picker-status-notice">
                          Showing placeholder stories until Jira is connected.
                        </p>
                      )}
                      {storiesState === 'loading' && <p className="team-picker-status">Loading stories…</p>}
                      {storiesState === 'ready' && stories.length === 0 && (
                        <p className="team-picker-status">No stories assigned to this team.</p>
                      )}
                      {storiesState === 'ready' && stories.length > 0 && (
                        <ul className="story-list">
                      {sortedStories.map((story) => (
                        <li key={story.key} className="story-card">
                          <div className="story-card-header">
                            <span className="story-key">{story.key}</span>
                            <span
                              className={`status status-${story.status.toLowerCase().replace(/\s+/g, '-')}`}
                            >
                              {story.status}
                            </span>
                          </div>
                          <p className="story-summary">{story.summary}</p>
                          <p className="story-meta">Assignee: {story.assignee ?? 'Unassigned'}</p>
                          {story.last_activity && <p className="story-activity">{story.last_activity}</p>}
                          {(story.branches.length > 0 || story.pull_requests.length > 0) && (
                            <div className="story-dev-links">
                              {story.branches.map((branch) => (
                                <span key={branch} className="dev-chip dev-chip-branch">
                                  {branch}
                                </span>
                              ))}
                              {story.pull_requests.map((pr) => (
                                <a
                                  key={pr.url}
                                  href={pr.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="dev-chip dev-chip-pr"
                                >
                                  {pr.title} · {pr.status}
                                </a>
                              ))}
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                    </>
                  )}
                </section>

                <section className="summary" aria-label="Execution summary">
                  <div>
                    <span>Active priorities</span>
                    <strong>3</strong>
                  </div>
                  <div>
                    <span>At risk</span>
                    <strong>1</strong>
                  </div>
                  <div>
                    <span>Due this week</span>
                    <strong>2</strong>
                  </div>
                </section>

                <section className="worklist" aria-labelledby="priorities-heading">
                  <div className="section-heading">
                    <div>
                      <p className="eyebrow">Today</p>
                      <h2 id="priorities-heading">Priorities</h2>
                    </div>
                    <span>Updated moments ago</span>
                  </div>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Work item</th>
                          <th>Owner</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {priorities.map((priority) => (
                          <tr key={priority.title}>
                            <td>{priority.title}</td>
                            <td>{priority.owner}</td>
                            <td>
                              <span
                                className={`status status-${priority.status.toLowerCase().replace(' ', '-')}`}
                              >
                                {priority.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              </div>
            </>
          ) : (
            <p className="team-detail-status">Select a team to see details.</p>
          )}
        </section>
      </div>
    </main>
  );
};
