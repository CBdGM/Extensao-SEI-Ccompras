import { defineConfig } from "vite";
import { resolve } from "path";
import { copyFileSync } from "fs";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

// Plugin to copy HTML pages and CSS assets to dist root after build
function copyExtensionAssets() {
  return {
    name: "copy-extension-assets",
    writeBundle() {
      const targets: [string, string][] = [
        ["src/sidebar/sidebar.html", "dist/sidebar.html"],
        ["src/sidebar/sidebar.css",  "dist/sidebar.css"],
        ["src/popup/popup.html",     "dist/popup.html"],
        ["src/popup/popup.css",      "dist/popup.css"],
        ["src/content/content.css",  "dist/content.css"],
      ];
      for (const [src, dest] of targets) {
        try {
          copyFileSync(resolve(__dirname, src), resolve(__dirname, dest));
        } catch {
          console.warn(`Could not copy ${src}`);
        }
      }
    },
  };
}

export default defineConfig({
  plugins: [copyExtensionAssets()],

  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        background: resolve(__dirname, "src/background/service-worker.ts"),
        content:    resolve(__dirname, "src/content/content.ts"),
        sidebar:    resolve(__dirname, "src/sidebar/sidebar.ts"),
        popup:      resolve(__dirname, "src/popup/popup.ts"),
      },
      output: {
        entryFileNames: "[name].js",
        // No hash — chunk names must be stable so manifest can reference them
        chunkFileNames: "chunks/[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
    target: "es2022",
    minify: false,
    sourcemap: true,
  },

  // manifest.json and icons/ live in public/ and are copied verbatim
  publicDir: "public",

  resolve: {
    alias: {
      "@shared": resolve(__dirname, "src/shared"),
    },
  },
});
