import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: true,
    proxy: {
      "/api": "http://localhost:8001",
      "/ws": {
        target: "ws://localhost:8001",
        ws: true,
      },
      "/health": "http://localhost:8001",
    },
  },
})
