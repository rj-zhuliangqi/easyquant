import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/static/spa/",
  build: {
    outDir: "app/static/spa",
    emptyOutDir: true,
    assetsDir: "assets",
    rollupOptions: {
      input: "frontend/index.html",
      output: {
        entryFileNames: "assets/app-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});
