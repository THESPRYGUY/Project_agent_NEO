import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/js/**/*.spec.ts'],
    exclude: ['tests/js/naics_cascade.spec.ts'],
    globals: true,
    environment: 'node',
    testTimeout: 15000,
  },
});
