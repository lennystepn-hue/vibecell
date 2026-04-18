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
      "/api": { target: "http://localhost:8000", changeOrigin: false },
    },
  },
  // @ts-expect-error vitest 2.x augments vite 5's UserConfig; project uses vite 6
  test: {
    environment: "jsdom",
    globals: true,
  },
});
