import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: run the API with `uvicorn api.index:app --port 8000` from the repo root.
export default defineConfig({
  plugins: [react()],
  server: {
    fs: { allow: [".."] },
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
});
