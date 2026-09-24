import { useEffect, useState } from 'react';

import { fetchTeams } from '@/api/teams';

type LoadState = 'loading' | 'ready';
type NotifyState = 'idle' | 'loading' | 'success' | 'error';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8888';
const DEFAULT_NOTIFY_MESSAGE =
  'High priority execution risks detected. Please review open PRs and stalled items, and help unblock owners today.';

// Shown until the Jira integration is connected and the API has real "Agile Team" data.
const FALLBACK_TEAMS = ['Team Alpha', 'Team Bravo', 'Team Charlie'];

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
  const [notifyState, setNotifyState] = useState<NotifyState>('idle');
  const [notifyMessage, setNotifyMessage] = useState('');

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

  const sendNotify = async () => {
    setNotifyState('loading');
    setNotifyMessage('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/alerts/notify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: 'Execution Partner Alert',
          message: DEFAULT_NOTIFY_MESSAGE,
        }),
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(payload.detail || 'Failed to send Teams alert');
      }

      setNotifyState('success');
      setNotifyMessage('Notification sent to Teams.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to send Teams alert';
      setNotifyState('error');
      setNotifyMessage(message);
    }
  };

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
                <div className="topbar-actions">
                  <button type="button" className="primary-action">
                    Add priority
                  </button>
                  <button
                    type="button"
                    className="secondary-action"
                    onClick={sendNotify}
                    disabled={notifyState === 'loading'}
                  >
                    {notifyState === 'loading' ? 'Sending...' : 'Notify Team'}
                  </button>
                </div>
              </div>

              <div className="team-detail-body">
                {notifyState !== 'idle' ? (
                  <p className={`notify-message notify-${notifyState}`} role="status">
                    {notifyMessage}
                  </p>
                ) : null}
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
