import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // The API runs on 8000. Proxying keeps the frontend origin-relative, so
    // nothing needs reconfiguring when it is deployed behind one host.
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
});
