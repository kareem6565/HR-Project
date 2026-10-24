import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Minimal test frontend for the FastAPI backend.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Optional same-origin fallback (not required when CORS is enabled).
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
