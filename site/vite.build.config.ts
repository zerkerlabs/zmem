import path from "path";
import { defineConfig } from "vite";

export default defineConfig({
  root: path.resolve(__dirname, "../site-build-entry"),
  base: "./",
  cacheDir: "/private/tmp/zmem-site-vite-cache",
  publicDir: path.resolve(__dirname, "public"),
  plugins: [],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, "dist"),
    emptyOutDir: true,
  },
});
