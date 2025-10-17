import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/js/**/*.spec.ts'],
    environment: 'node',
    testTimeout: 15000,
  },
});

