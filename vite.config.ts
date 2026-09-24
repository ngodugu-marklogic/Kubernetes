/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': resolve(import.meta.dirname, './src'),
      },
    },
    server: {
      proxy: {
        '/api': {
          target: env.BACKEND_PROXY_TARGET || 'http://localhost:8888',
          changeOrigin: true,
          ws: true,
        },
      },
      watch: {
        ignored: ['**/coverage/**'],
        // Windows bind mounts into the Linux container don't propagate inotify events reliably.
        usePolling: true,
        interval: 300,
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
    },
  };
});
