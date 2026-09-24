import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Thin static client over the FastAPI backend. No SSR.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
});
