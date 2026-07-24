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
        // P3-5: 大依赖单独成 chunk，配合路由懒加载减小首屏体积
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("echarts") || id.includes("zrender")) return "echarts";
          if (id.includes("marked") || id.includes("dompurify")) return "markdown";
          if (id.includes("/vue/") || id.includes("@vue") || id.includes("vue-router") || id.includes("@tanstack")) return "vue-vendor";
          return undefined;
        },
      },
    },
  },
});
