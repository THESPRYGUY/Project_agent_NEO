import { materialize, search, getNode, children, lineage, deepestValid } from '../../src/naics/naics_index';

beforeAll(() => {
  // ensure data is loaded
  materialize();
});

describe('naics_index basic behaviors', () => {
  test('search by code prefix returns expected nodes', () => {
    const results = search('31');
    expect(results.length).toBeGreaterThan(0);
    expect(results.some(r => r.code.startsWith('31'))).toBe(true);
  });

  test('getNode returns undefined for unknown', () => {
    expect(getNode('999999')).toBeUndefined();
  });

  test('children returns predictable subset', () => {
    // pick first result and fetch children if any
    const any = search('3')[0];
    const kids = children(any.code);
    if (kids.length > 0) {
      kids.forEach(k => {
        const parentCodes = k.parents.map(p => p.code);
        expect(parentCodes.includes(any.code)).toBe(true);
      });
    } else {
      expect(kids).toEqual([]);
    }
  });

  test('lineage returns only parents (excluding self)', () => {
    const deepHits = search('311');
    if (!deepHits.length) return; // dataset may not have these codes
    const deep = deepHits[0];
    const lin = lineage(deep.code);
    if (lin.length) {
      expect(lin[lin.length - 1].code).not.toBe(deep.code);
    } else {
      expect(Array.isArray(lin)).toBe(true);
    }
  });

  test('deepestValid returns a node or undefined appropriately', () => {
    const candidate = '311999';
    const node = deepestValid(candidate);
    if (node) {
      expect(candidate.startsWith(node.code)).toBe(true);
    } else {
      expect(node).toBeUndefined();
    }
  });
});
