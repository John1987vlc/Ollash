/**
 * Vitest configuration for Ollash frontend component tests.
 *
 * Tests live in tests/unit/frontend/components/ and use jsdom
 * so that window / document / DOM APIs are available.
 */
import { defineConfig } from 'vitest/config';

export default defineConfig({
    test: {
        // jsdom provides window, document, and full DOM APIs
        environment: 'jsdom',

        // Match test_*.js files in the frontend components folder
        include: ['tests/unit/frontend/**/*.js'],

        // Exclude generated artefacts and fixtures
        exclude: [
            '**/node_modules/**',
            '**/dist/**',
            '**/__pycache__/**',
            '**/*.pyc',
        ],

        // Reporter: verbose in CI, default locally
        reporter: process.env.CI ? 'verbose' : 'default',

        // Coverage (optional — only when running npm run test:coverage)
        coverage: {
            provider: 'v8',
            include: ['frontend/static/js/components/**/*.js'],
            exclude: ['**/node_modules/**'],
            reporter: ['text', 'html', 'json'],
        },
    },
});
