import path from "path"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  base: './',
  cacheDir: "/private/tmp/zmem-site-vite-cache",
  plugins: [],
  esbuild: {
    jsx: "automatic",
    jsxImportSource: "react",
  },
  server: {
    port: 3000,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
