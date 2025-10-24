import { vi } from 'vitest';

// Stub clipboard API for copy tests
// @ts-ignore
global.navigator = {
  clipboard: {
    writeText: vi.fn().mockResolvedValue(void 0),
  },
} as any;

// No global cleanup: tests manage their own DOM resets
