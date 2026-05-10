import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// https://vite.dev/config/
export default defineConfig({
  base: process.env.NODE_ENV === 'production' ? '/static/' : '/',
  plugins: [svelte()],
  build: {
    outDir: '../src/interfaces/web/dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/sessions': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/api-keys': 'http://localhost:8000',
      '/settings': 'http://localhost:8000',
    },
  },
})
