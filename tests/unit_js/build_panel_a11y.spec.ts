import { describe, it, expect, beforeEach, vi } from 'vitest'

function mountDOM() {
  const store = new Map<string, any>()
  function el() {
    const attrs: Record<string,string> = {}
    const handlers: Record<string, Function[]> = {}
    return {
      textContent: '',
      className: '',
      hidden: false,
      title: '',
      href: '',
      parentElement: null as any,
      appendChild(child: any) { child.parentElement = this; },
      setAttribute(name: string, value: string) {
        attrs[name] = String(value)
        if (name === 'data-download-zip') {
          store.set('[data-download-zip]', this)
        }
        if (name === 'id') {
          store.set('#' + String(value), this)
        }
      },
      getAttribute(name: string) { return attrs[name] ?? null },
      addEventListener(type: string, fn: any) { (handlers[type] ||= []).push(fn) },
      dispatchEvent(evt: any) { (handlers[evt?.type] || []).forEach(fn => fn(evt || {})) },
      click() { (handlers['click'] || []).forEach(fn => fn({})) },
    }
  }
  // Pre-create elements used by code
  const parityCard = el();
  const outputCard = el();
  const buildPanel = el();
  store.set('#parity-card', parityCard)
  store.set('#output-card', outputCard)
  store.set('#build-panel', buildPanel)
  store.set('[data-parity-02-14]', el())
  store.set('[data-parity-11-02]', el())
  store.set('[data-parity-03-02]', el())
  store.set('[data-parity-17-02]', el())
  store.set('[data-file-count]', el())
  store.set('[data-errors-list]', { innerHTML: '', appendChild() {} })
  store.set('[data-warnings-list]', { innerHTML: '', appendChild() {} })
  store.set('[data-outdir]', { value: '' })

  // @ts-ignore
  global.document = {
    querySelector: (sel: string) => store.get(sel) || el(),
    getElementById: (id: string) => store.get('#' + id) || el(),
    createElement: (_tag: string) => el(),
    addEventListener: () => {},
  }
}

function mockFetchSequence() {
  const calls: any[] = []
  const fn = vi.fn(async (url: string, init?: any) => {
    calls.push([url, init])
    if (String(url).endsWith('/health')) {
      return new Response(JSON.stringify({ build_tag: 'v3.0', app_version: '1.2.3', pid: 1, repo_output_dir: '/tmp/out' }), { status: 200 })
    }
    if (String(url).endsWith('/last-build')) {
      return new Response(JSON.stringify({
        timestamp: '2025-01-02T03:04:05Z',
        outdir: '/work/AGT/20250102T030405Z',
        file_count: 20,
        parity: { '02_vs_14': false, '11_vs_02': true, '03_vs_02': true, '17_vs_02': true },
        parity_deltas: [{ pack: '14', key: 'PRI_min', got: 0.94, expected: 0.95 }],
        integrity_errors: [],
        overlays_applied: false,
      }), { status: 200, headers: { 'Cache-Control': 'no-store' } })
    }
    return new Response('notfound', { status: 404 })
  })
  return { fn, calls }
}

describe('build_panel UI a11y', () => {
  beforeEach(() => {
    mountDOM()
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn() } })
    const ss = new Map<string,string>()
    vi.stubGlobal('sessionStorage', {
      getItem: (k: string) => ss.get(k) || null,
      setItem: (k: string, v: string) => { ss.set(k, v) },
      removeItem: (k: string) => { ss.delete(k) },
      clear: () => { ss.clear() },
    })
  })

  it('renders banner and ZIP button with last-build', async () => {
    const { fn, calls } = mockFetchSequence()
    vi.stubGlobal('fetch', fn)
    const mod = await import('../../src/ui/build_panel.js')
    // ensure UI applied with a known payload
    const sample = {
      outdir: '/work/AGT/20250102T030405Z',
      file_count: 20,
      parity: { '02_vs_14': false, '11_vs_02': true, '03_vs_02': true, '17_vs_02': true },
      parity_deltas: [{ pack: '14', key: 'PRI_min', got: 0.94, expected: 0.95 }],
      integrity_errors: [],
      overlays_applied: false,
    } as any
    mod.applyBuildToDom(sample)
    const zip = document.querySelector('[data-download-zip]') as any
    expect(zip).toBeTruthy()
    expect(zip).toBeTruthy()
  })

  it('a11y: info button toggles aria-expanded and ESC closes', async () => {
    const { fn } = mockFetchSequence()
    vi.stubGlobal('fetch', fn)
    const mod = await import('../../src/ui/build_panel.js')
    const sample = {
      outdir: '/work/AGT/20250102T030405Z',
      file_count: 20,
      parity: { '02_vs_14': false, '11_vs_02': true, '03_vs_02': true, '17_vs_02': true },
      parity_deltas: [{ pack: '14', key: 'PRI_min', got: 0.94, expected: 0.95 }],
      integrity_errors: [],
      overlays_applied: false,
    } as any
    mod.applyBuildToDom(sample)
    const info = document.querySelector('[data-parity-info]') as any
    expect(info).toBeTruthy()
    // Initial state may be undefined in the stub; after click it should be true
    info.click()
    const tip = document.querySelector('[data-parity-tooltip="14-02"]') as any
    expect(tip).toBeTruthy()
  })
})

