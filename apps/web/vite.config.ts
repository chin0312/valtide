import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Thin static client over the FastAPI backend. No SSR.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const proxy = { target: env.VITE_API_BASE_URL || "http://localhost:8000", changeOrigin: true };
  return {
    plugins: [react(), tailwindcss()],
    // Same-origin reads preserve the historical source header during development.
    server: { port: 5173, proxy: { "/api": proxy, "/health": proxy } },
  };
});
