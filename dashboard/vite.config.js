// vite.config.js — Dashboard build configuration
// Phase: 8 — Visualization & Dashboard
// Status: STUB — to be configured in Phase 8
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
  optimizeDeps: {
    exclude: [
      'workbox-precaching',
      'workbox-strategies',
      'workbox-routing',
      'workbox-expiration',
    ],
  },
});
