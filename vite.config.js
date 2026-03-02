import { defineConfig } from 'vite';
import path from 'path';

/**
 * Vite configuration for Ollash frontend bundling.
 *
 * Output:   frontend/static/dist/
 * Manifest: frontend/static/dist/.vite/manifest.json  (FastAPI reads at runtime)
 *
 * Feature flag:
 *   Set USE_VITE_ASSETS=true in .env to use bundled assets.
 *   Development mode (npm run dev) runs Vite HMR on port 5173.
 *
 * Build command:  npm run build
 * Type check:     npm run typecheck
 * Lint:           npm run lint
 */
export default defineConfig({
  root: 'frontend/static',

  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'frontend/static/js'),
    },
  },

  build: {
    outDir: path.resolve(__dirname, 'frontend/static/dist'),
    emptyOutDir: true,
    manifest: true,

    rollupOptions: {
      input: {
        // Core bundle — loaded on every page
        main: path.resolve(__dirname, 'frontend/static/js/index.ts'),
      },
    },

    // Minify for production
    minify: 'esbuild',
    sourcemap: false,

    // Inline assets < 4 kB as base64
    assetsInlineLimit: 4096,
  },

  // Base URL for assets — FastAPI/Flask serves from /static/dist/
  base: '/static/dist/',

  // Vitest configuration
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['frontend/static/js/**/*.{test,spec}.{js,ts}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['frontend/static/js/**/*.{js,ts}'],
      exclude: ['frontend/static/js/**/*.{test,spec}.{js,ts}', 'frontend/static/dist/**'],
    },
  },
});
