import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/ui/setup.ts'],
    include: ['tests/unit_js/**/*.spec.ts'],
    coverage: {
      enabled: true,
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/ui/build_panel.js'],
      thresholds: { lines: 80, functions: 80, statements: 80, branches: 70 },
    },
  },
});
