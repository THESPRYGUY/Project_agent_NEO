import { describe, it, expect } from 'vitest';
import { scorePersonaFit } from '../../src/ui/persona_math.js';

describe('persona_math', () => {
  it('computes simple fit score', () => {
    const s = scorePersonaFit({ role: 'CAIO', tone: 'crisp' } as any);
    expect(typeof s).toBe('number');
  });
});

