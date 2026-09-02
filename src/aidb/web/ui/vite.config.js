import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// FastAPI: GET / -> static/index.html ; /static mounted on the same folder.
export default defineConfig({
  plugins: [vue()],
  base: "/static/",
  build: {
    outDir: "../static",
    emptyOutDir: true,
    assetsDir: "assets",
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8787",
    },
  },
});
