import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// vitest.config doesn't enable test.globals, so @testing-library/react's automatic
// afterEach-based cleanup never registers; unmount rendered trees explicitly instead.
afterEach(() => {
  cleanup();
});
