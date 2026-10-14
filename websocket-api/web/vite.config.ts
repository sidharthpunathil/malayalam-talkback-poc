import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies the API to the FastAPI backend on :8003.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8003',
      '/ws': { target: 'ws://127.0.0.1:8003', ws: true },
    },
  },
})
