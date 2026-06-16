import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const agentTarget = env.VITE_AGENT_DEV_URL || 'http://localhost:8000'

  return {
    // `./` emits asset URLs relative to index.html, so the SAME build serves at
    // `/`, `/valuestocks/`, or any subpath a reverse proxy mounts it on. Runtime
    // API URLs are derived from document.baseURI (see src/lib/apiBase.ts).
    // Override with VITE_BASE=/foo/ only if you need an absolute-prefix build.
    base: env.VITE_BASE || './',
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: agentTarget,
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ''),
          // SSE: don't buffer, hold the connection open for long agent runs.
          configure: (proxy) => {
            proxy.on('proxyReq', (proxyReq) => {
              proxyReq.setHeader('Accept', 'text/event-stream')
            })
          },
          ws: false,
          timeout: 0,
          proxyTimeout: 0,
        },
      },
    },
  }
})
