import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { App } from '@/App';

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({ teams: ['Platform', 'Growth'] }),
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
  });
});
