import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8765"
    }
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("@element-plus/icons-vue")) {
            return "vendor-element-icons";
          }
          if (id.includes("node_modules/element-plus")) {
            return "vendor-element";
          }
          if (id.includes("node_modules")) {
            return "vendor";
          }
        },
      },
    },
  }
});
