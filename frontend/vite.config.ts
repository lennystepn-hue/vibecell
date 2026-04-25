// frontend/vite.config.ts
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.HANGAR_E2E_BACKEND_URL ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          three: ["three"],
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
  // @ts-expect-error vitest 2.x augments vite 5's UserConfig; project uses vite 6
  test: {
    environment: "jsdom",
    globals: true,
    // e2e/ contains Playwright specs (run via `pnpm e2e`, not vitest).
    // Without this exclude vitest picks them up + crashes on Playwright's
    // "test() not expected here" guard.
    exclude: ["**/node_modules/**", "**/dist/**", "**/e2e/**"],
  },
});
