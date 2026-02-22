import { defineConfig } from 'vite';
import path from 'path';

/**
 * Vite configuration for Ollash frontend bundling.
 *
 * Output:  frontend/static/dist/
 * Manifest: frontend/static/dist/manifest.json  (Flask reads this at runtime)
 *
 * Feature flag:
 *   Set USE_VITE_ASSETS=true in .env to use bundled assets in production.
 *   Development mode continues to serve files directly via Flask url_for().
 *
 * Build command: npm run build
 */
export default defineConfig({
  root: 'frontend/static',

  build: {
    outDir: path.resolve(__dirname, 'frontend/static/dist'),
    emptyOutDir: true,
    manifest: true,

    rollupOptions: {
      input: {
        // Core bundle — loaded on every page
        main: path.resolve(__dirname, 'frontend/static/js/index.js'),
      },
    },

    // Minify for production
    minify: 'esbuild',
    sourcemap: false,

    // Inline assets < 4 kB as base64
    assetsInlineLimit: 4096,
  },

  // Base URL for assets — Flask will serve from /static/dist/
  base: '/static/dist/',
});
