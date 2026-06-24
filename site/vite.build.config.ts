import path from "path";
import { defineConfig } from "vite";

const siteRoot = __dirname;
const siteNodeModules = path.resolve(siteRoot, "node_modules");

export default defineConfig({
  root: path.resolve(siteRoot, "../site-build-entry"),
  base: "./",
  cacheDir: "/private/tmp/zmem-site-vite-cache",
  publicDir: path.resolve(siteRoot, "public"),
  plugins: [],
  esbuild: {
    jsx: "automatic",
    jsxImportSource: "react",
  },
  resolve: {
    dedupe: ["react", "react-dom"],
    alias: {
      "@": path.resolve(siteRoot, "./src"),
      react: path.resolve(siteNodeModules, "react"),
      "react-dom": path.resolve(siteNodeModules, "react-dom"),
      "react-dom/client": path.resolve(siteNodeModules, "react-dom/client.js"),
      "react/jsx-runtime": path.resolve(siteNodeModules, "react/jsx-runtime.js"),
      "react/jsx-dev-runtime": path.resolve(siteNodeModules, "react/jsx-dev-runtime.js"),
    },
  },
  build: {
    outDir: path.resolve(siteRoot, "dist"),
    emptyOutDir: true,
  },
});
