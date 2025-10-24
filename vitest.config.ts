import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/ui/setup.ts'],
    testTimeout: 15000,
    include: ['tests/js/**/*.spec.ts', 'tests/ui/**/*.spec.ts'],
    exclude: ['tests/js/naics_cascade.spec.ts'],
  },
});
