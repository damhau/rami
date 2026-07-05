import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Backend host:port the dev server proxies API + WebSocket traffic to.
// Override with VITE_API_TARGET (e.g. "localhost:8100") if 8000 is taken.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_TARGET || "localhost:8000";
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: Number(env.VITE_PORT || 5173),
      proxy: {
        "/api": { target: `http://${apiTarget}`, changeOrigin: true },
        "/ws": { target: `ws://${apiTarget}`, ws: true },
      },
    },
  };
});
