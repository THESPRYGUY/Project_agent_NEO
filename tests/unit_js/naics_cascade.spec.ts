import { describe, it, expect } from 'vitest';
import { loadNaics } from '../../src/ui/naics_cascade.js';

describe('naics cascade (unit subset)', () => {
  it('loads top-level entries without network', async () => {
    const data = await loadNaics({ offline: true } as any);
    expect(Array.isArray(data)).toBe(true);
  });
});

