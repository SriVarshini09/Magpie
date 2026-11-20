import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Shared file, owned by the coordinator (OWNERSHIP.md).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  // One .env at the repo root serves both apps; only VITE_* names reach the browser.
  envDir: "..",
  server: { port: 5173, strictPort: true },
  build: {
    // Code splitting (quality bar Q2). The 3D views are behind React.lazy (components/stage/*Scene), so three.js
    // and its helpers land in a chunk the landing page only asks for once it has painted. The other groups are
    // still loaded up front, but in parallel and cached apart from the app's own code.
    rolldownOptions: {
      output: {
        codeSplitting: {
          // Off, or the three.js group would swallow React (its dependency) and be loaded by every page.
          includeDependenciesRecursively: false,
          groups: [
            { name: "three", test: /node_modules[\\/](three|three-stdlib|three-mesh-bvh|@react-three|postprocessing|n8ao|maath|camera-controls|urdf-loader|meshline|troika-[\w-]+|@monogrid|detect-gpu|stats-gl|stats\.js|suspend-react|its-fine|tunnel-rat|hls\.js|@mediapipe|webgl-sdf-generator|bidi-js|glsl-noise|@use-gesture)[\\/]/, priority: 30 },
            { name: "react", test: /node_modules[\\/](react|react-dom|react-router|scheduler)[\\/]/, priority: 20 },
            { name: "diagram", test: /node_modules[\\/](@xyflow|d3-[\w-]+|classcat)[\\/]/, priority: 10 },
            { name: "checkout", test: /node_modules[\\/](@stripe|@shopify)[\\/]/, priority: 10 },
          ],
        },
      },
    },
    // The three.js chunk is about 1.4 MB before gzip and is only ever loaded on demand.
    chunkSizeWarningLimit: 1500,
  },
});
