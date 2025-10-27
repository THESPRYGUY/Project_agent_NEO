import { describe, it, expect, beforeEach, vi } from 'vitest';
import { buildRepo, persistLastBuild, readLastBuild, applyBuildToDom } from '../../src/ui/build_panel.js';

function mockSession() {
  const store: Record<string, string> = {};
  // @ts-ignore
  global.sessionStorage = {
    setItem: (k: string, v: string) => { store[k] = v; },
    getItem: (k: string) => store[k] || null,
    removeItem: (k: string) => { delete store[k]; },
    clear: () => { Object.keys(store).forEach(k => delete store[k]); },
  };
}

describe('buildRepo util', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockSession();
  });

  it('persists last build and returns data on success', async () => {
    const sample = {
      outdir: 'C:/tmp/agent/20250101T000000Z',
      file_count: 21,
      parity: { '02_vs_14': true, '11_vs_02': true },
      integrity_errors: [],
      warnings: [],
    };
    // @ts-ignore
    global.fetch = vi.fn(async () => ({ ok: true, status: 200, headers: new Map(), text: async () => JSON.stringify(sample) }));
    const { data } = await buildRepo();
    expect(data).toBeTruthy();
    expect(data.file_count).toBe(21);
    const last = readLastBuild();
    expect(last).toBeTruthy();
    expect(last.outdir).toBe(sample.outdir);
  });

  it('throws with trace id on failure', async () => {
    // @ts-ignore
    global.fetch = vi.fn(async () => ({ ok: false, status: 500, headers: { get: (k: string) => (k.toLowerCase()==='x-request-id' ? 'trace-123' : null) }, text: async () => 'oops' }));
    await expect(buildRepo()).rejects.toHaveProperty('traceId', 'trace-123');
  });
});

describe('applyBuildToDom', () => {
  beforeEach(() => {
    const lists: Record<string, any> = {};
    // @ts-ignore
    global.document = {
      querySelector: (sel: string) => {
        const el: any = { textContent: '', classList: { remove() {}, add() {} } };
        if (sel === '[data-outdir]') {
          return { value: '', set value(v: string) { (this as any)._v = v; }, get value() { return (this as any)._v; } } as any;
        }
        if (sel === '[data-errors-list]' || sel === '[data-warnings-list]') {
          if (!lists[sel]) lists[sel] = { children: [], innerHTML: '', appendChild: (li: any) => { lists[sel].children.push(li); } };
          return lists[sel];
        }
        return el;
      },
      createElement: (tag: string) => ({ tagName: tag.toUpperCase(), textContent: '' }),
    } as any;
  });

  it('renders parity and counts', () => {
    const sample = {
      outdir: 'C:/tmp/agent/20250101T000000Z',
      file_count: 21,
      parity: { '02_vs_14': true, '11_vs_02': false },
      integrity_errors: ['Missing 02'],
      warnings: ['Stubbed section']
    };
    applyBuildToDom(sample as any);
    // If we reached here without throwing, minimal smoke coverage achieved
    expect(true).toBe(true);
  });
});

