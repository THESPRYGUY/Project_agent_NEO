import { suggestPersona } from '../../src/persona/suggester';

describe('suggestPersona', () => {
  it('recommends an analytical partner for finance analysts', () => {
    const suggestion = suggestPersona({
      domain: 'Finance',
      role: 'Enterprise Analyst',
      operatorType: 'INTJ',
      preferences: { autonomy: 60, confidence: 70, collaboration: 45 },
    });
    expect(suggestion.code).toBe('INTJ');
    expect(suggestion.rationale.join(' ')).toContain('Finance');
  });

  it('prioritises collaborative personas when sliders emphasise people work', () => {
    const suggestion = suggestPersona({
      domain: 'Human Resources',
      role: 'Knowledge Manager',
      operatorType: 'ISTJ',
      preferences: { autonomy: 35, confidence: 55, collaboration: 80 },
    });
    expect(['ENFJ', 'INFJ', 'ISFJ']).toContain(suggestion.code);
    expect(suggestion.preferenceNotes.length).toBeGreaterThan(0);
  });
});
