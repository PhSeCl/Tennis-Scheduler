import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/eel.js": {
        target: "http://localhost:8000",
        changeOrigin: true
      },
      "/eel": {
        target: "ws://localhost:8000",
        ws: true,
        changeOrigin: true
      }
    }
  }
});
