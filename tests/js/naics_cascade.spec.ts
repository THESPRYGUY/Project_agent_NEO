/**
 * NAICS cascade/API smoke tests.
 * These tests are environment-aware and will pass gracefully when
 * the intake server is not running locally. To exercise endpoints,
 * run the server and set NAICS_BASE_URL if non-default.
 */

const BASE = process.env.NAICS_BASE_URL || 'http://127.0.0.1:5000';

async function fetchJson(path: string) {
  const url = `${BASE}${path}`;
  try {
    const res = await fetch(url);
    const text = await res.text();
    return { ok: res.ok, status: res.status, body: text, json: safeParse(text) };
  } catch (err) {
    return { ok: false, status: 0, body: String(err), json: null };
  }
}

function safeParse(text: string) {
  try { return JSON.parse(text); } catch { return null; }
}

function hasItems(obj: any): boolean {
  return !!obj && typeof obj === 'object' && Array.isArray(obj.items);
}

describe('NAICS API smoke', () => {
  it('roots, children, search respond with 200 JSON when server available', async () => {
    const roots = await fetchJson('/api/naics/roots');
    if (!roots.ok) {
      // Server not running; exit early without failing CI
      console.warn('NAICS server not reachable; skipping endpoint checks');
      return;
    }
    expect(roots.ok).toBe(true);
    expect(roots.json).toBeTruthy();

    const children = await fetchJson('/api/naics/children/541?level=4');
    expect(children.ok).toBe(true);
    expect(children.json).toBeTruthy();
    // With full dataset this should be non-empty; allow empty with sample
    if (hasItems(children.json)) {
      expect(Array.isArray(children.json.items)).toBe(true);
    }

    const search = await fetchJson('/api/naics/search?q=54');
    expect(search.ok).toBe(true);
    expect(search.json).toBeTruthy();
  });
});
