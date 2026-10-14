import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies the REST API to the FastAPI backend on :8002.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5172,
    proxy: { '/api': 'http://127.0.0.1:8002' },
  },
})
