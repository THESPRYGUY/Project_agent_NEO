import { compatibilityScore, roleFitScore, blendedScore } from '../../src/persona/math';

describe('compatibilityScore', () => {
  it('returns perfect score for identical MBTI types', () => {
    const result = compatibilityScore('INTJ', 'INTJ');
    expect(result.score).toBe(100);
    expect(result.matches).toBe(4);
    expect(result.mismatches).toBe(0);
  });

  it('penalises mismatched axes', () => {
    const result = compatibilityScore('INTJ', 'ESFP');
    expect(result.score).toBeLessThan(60);
    expect(result.matches).toBeLessThan(3);
  });
});

describe('roleFitScore', () => {
  it('follows domain and role priors', () => {
    const result = roleFitScore('Finance', 'Enterprise Analyst', 'ENTJ');
    expect(result.score).toBeGreaterThan(80);
    expect(result.factors[0]).toContain('Finance');
  });

  it('returns baseline when domain missing', () => {
    const result = roleFitScore(null, null, 'INTP');
    expect(result.score).toBe(60);
  });
});

describe('blendedScore', () => {
  it('mixes compatibility and role fit with preference weighting', () => {
    const score = blendedScore({ compatibility: 90, roleFit: 60, preferenceWeight: 0.75 });
    expect(score).toBeGreaterThan(70);
    expect(score).toBeLessThanOrEqual(90);
  });
});
