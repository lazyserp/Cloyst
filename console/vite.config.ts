import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  base: '/static/',
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../core/console',
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8001',
      '/metrics': 'http://127.0.0.1:8001',
    },
  },
});
