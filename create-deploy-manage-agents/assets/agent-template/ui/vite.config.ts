import {defineConfig} from 'vite';

// Served by the agent at /ui; assets at /ui/assets. `npm run dev` proxies API calls.
export default defineConfig({
  base: '/ui/',
  server: {proxy: {'/a2ui': 'http://127.0.0.1:8080'}},
});
