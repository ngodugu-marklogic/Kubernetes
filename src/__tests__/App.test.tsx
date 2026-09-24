import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '@/App';

describe('App', () => {
  beforeEach(() => {
    HTMLElement.prototype.scrollIntoView = vi.fn();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => ({
        ok: true,
        json: async () =>
          url.includes('/stories')
            ? {
                stories: [
                  {
                    key: 'EX-1',
                    summary: 'Ship it',
                    status: 'In Progress',
                    assignee: 'Jamie Lee',
                    last_activity: 'Jamie Lee updated the status yesterday',
                    branches: ['feature/ex-1'],
                    pull_requests: [
                      { title: 'Ship it PR', url: 'https://example.com/pr/1', status: 'Open' },
                    ],
                  },
                ],
              }
            : { teams: ['Platform', 'Growth'] },
      }))
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('renders the workspace and the fetched teams', async () => {
    render(<App />);

    expect(screen.getByRole('heading', { name: 'Execution Partner' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Choose a team' })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Platform' })).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Growth' })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Ship it')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Open assistant' }));
    expect(screen.getByLabelText('Jira context: Platform')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Growth' }));
    expect(screen.getByLabelText('Jira context: Growth')).toBeInTheDocument();
  });

  it('sends a generic teams notification when notify button is clicked', async () => {
    const fetchSpy = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/stories')) {
        return {
          ok: true,
          json: async () => ({ stories: [] }),
        } as Response;
      }
      if (url.includes('/api/v1/teams')) {
        return {
          ok: true,
          json: async () => ({ teams: ['Platform', 'Growth'] }),
        } as Response;
      }
      if (url.includes('/api/v1/alerts/notify')) {
        return {
          ok: true,
          json: async () => ({ delivered: true }),
        } as Response;
      }
      return {
        ok: false,
        json: async () => ({}),
      } as Response;
    });
    vi.stubGlobal('fetch', fetchSpy);

    render(<App />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Platform' })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: 'Notify Team' }));

    await waitFor(() =>
      expect(fetchSpy).toHaveBeenCalledWith('http://localhost:8888/api/v1/alerts/notify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: 'Execution Partner Alert',
          message:
            'High priority execution risks detected. Please review open PRs and stalled items, and help unblock owners today.',
        }),
      })
    );

    expect(screen.getByRole('status')).toHaveTextContent('Notification sent to Teams.');
  });
});
