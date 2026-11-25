import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// The dev server proxies the Django API and media files, so the browser sees one
// origin: the httpOnly refresh cookie and CSRF work without any CORS setup.
const backend = process.env.VITE_BACKEND_URL ?? "http://127.0.0.1:8000"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: false },
      "/media": { target: backend, changeOrigin: false },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Long-lived vendor chunks; the portals are lazy-loaded separately.
        manualChunks(id) {
          if (id.includes("node_modules")) {
            if (/react-dom|react-router|scheduler|\/react\//.test(id)) return "react"
            if (id.includes("@tanstack")) return "query"
          }
        },
      },
    },
  },
})
