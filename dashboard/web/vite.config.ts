import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/frames': 'http://localhost:8000',
      '/thumbs': 'http://localhost:8000',
    },
  },
  // maplibre-gl spins up its own Web Worker for vector tile parsing; Vite's
  // dev-time esbuild pre-bundling of it breaks that worker's URL resolution
  // ("Worker failed to load") -- this is maplibre-gl's own documented Vite
  // workaround, not something specific to this app.
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
})
