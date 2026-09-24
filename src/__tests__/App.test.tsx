import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '@/App';

describe('App', () => {
  beforeEach(() => {
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
                    pull_requests: [{ title: 'Ship it PR', url: 'https://example.com/pr/1', status: 'Open' }],
                  },
                ],
              }
            : { teams: ['Platform', 'Growth'] },
      })),
    );
  });

  afterEach(() => {
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
  });
});
