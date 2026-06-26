import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Dev server runs on :5173 and proxies REST to the FastAPI backend on :8080 so
// the new UI can be previewed alongside the existing one. rosbridge (ws://:9090)
// is reached directly via the host network, so it needs no proxy.
// Production build (npm run build) emits static assets served by FastAPI.
export default defineConfig({
  plugins: [svelte()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': 'http://localhost:80',
    },
  },
});
