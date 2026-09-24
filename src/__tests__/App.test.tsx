import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { App } from '@/App';

describe('App', () => {
  it('renders the execution workspace and its priorities', () => {
    render(<App />);

    expect(screen.getByRole('heading', { name: 'Execution Partner' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Priorities' })).toBeInTheDocument();
    expect(screen.getByText('Review launch criteria')).toBeInTheDocument();
  });
});
