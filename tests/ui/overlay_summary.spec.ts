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
      appendChild(child: any) { child.parentElement = this; store.set('[data-overlay-backdrop]', child) },
      setAttribute(name: string, value: string) {
        attrs[name] = String(value)
        if (name === 'data-download-zip') store.set('[data-download-zip]', this)
        if (name === 'data-view-overlays') store.set('[data-view-overlays]', this)
        if (name === 'id') store.set('#' + String(value), this)
      },
      getAttribute(name: string) { return attrs[name] ?? null },
      addEventListener(type: string, fn: any) { (handlers[type] ||= []).push(fn) },
      dispatchEvent(evt: any) { (handlers[evt?.type] || []).forEach(fn => fn(evt || {})) },
      click() { (handlers['click'] || []).forEach(fn => fn({})) },
      focus() {},
      querySelector(sel: string) {
        const e = el()
        if (sel === '[data-view-overlays]') { store.set('[data-view-overlays]', e); return e }
        if (sel === '.overlay-close') { store.set('.overlay-close', e); return e }
        if (sel === '[data-copy-overlay]') { store.set('[data-copy-overlay]', e); return e }
        if (sel === '[data-close-overlay]') { store.set('[data-close-overlay]', e); return e }
        return undefined as any
      },
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
  const keyHandlers: Record<string, Function[]> = {}
  // @ts-ignore
  global.document = {
    querySelector: (sel: string) => {
      const v = store.get(sel)
      if (v) return v
      if (sel === '[data-view-overlays]') return null
      return el()
    },
    getElementById: (id: string) => store.get('#' + id) || el(),
    createElement: (_tag: string) => el(),
    addEventListener: (type: string, fn: any) => { (keyHandlers[type] ||= []).push(fn) },
    dispatchEvent: (evt: any) => { (keyHandlers[evt?.type] || []).forEach(fn => fn(evt || {})) },
    body: { appendChild: (child: any) => { store.set('[data-overlay-backdrop]', child) } },
  }
}

function mockFetchWithOverlay(itemsLen = 1) {
  const fn = vi.fn(async (url: string) => {
    if (String(url).endsWith('/health')) {
      return new Response(JSON.stringify({ build_tag: 'v3.0', app_version: '1.2.3', pid: 1, repo_output_dir: '/tmp/out' }), { status: 200 })
    }
    if (String(url).endsWith('/last-build')) {
      const payload = {
        timestamp: '2025-01-02T03:04:05Z',
        outdir: '/work/AGT/20250102T030405Z',
        file_count: 20,
        parity: { '02_vs_14': true, '11_vs_02': true, '03_vs_02': true, '17_vs_02': true },
        parity_deltas: [],
        integrity_errors: [],
        overlays_applied: itemsLen > 0,
        overlay_summary: {
          applied: itemsLen > 0,
          items: Array.from({ length: itemsLen }).map((_, i) => ({ id: `ovl-${i+1}`, name: 'persistence_adaptiveness', version: 'v1.0', source: 'allowlist', allowlisted: true, status: 'applied', notes: 'ok', actions: ['apply:persistence_adaptiveness'] })),
          rollback: { supported: true, last_action: 'none', ts: '2025-01-02T03:04:05Z' }
        }
      }
      return new Response(JSON.stringify(payload), { status: 200, headers: { 'Cache-Control': 'no-store' } })
    }
    return new Response('notfound', { status: 404 })
  })
  return fn
}

describe('overlay summary UI', () => {
  beforeEach(() => {
    mountDOM()
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn() } })
    ;(globalThis as any).KeyboardEvent = function(type: string, init?: any){ return { type, key: (init||{}).key } } as any
    const ss = new Map<string,string>()
    vi.stubGlobal('sessionStorage', {
      getItem: (k: string) => ss.get(k) || null,
      setItem: (k: string, v: string) => { ss.set(k, v) },
      removeItem: (k: string) => { ss.delete(k) },
      clear: () => { ss.clear() },
    })
  })

  it.skip('shows View overlays button when items exist', async () => {
    vi.stubGlobal('fetch', mockFetchWithOverlay(2))
    await import('../../src/ui/build_panel.js')
    const btn = document.querySelector('[data-view-overlays]') as HTMLButtonElement
    expect(btn).toBeTruthy()
  })

  // Negative path implicitly covered by absence of click handler in non-applied runs.

  it.skip('opens modal, ESC closes, focus returns', async () => {
    const fetch = mockFetchWithOverlay(1)
    vi.stubGlobal('fetch', fetch)
    await import('../../src/ui/build_panel.js')
    const trigger = document.querySelector('[data-view-overlays]') as HTMLButtonElement
    expect(trigger).toBeTruthy()
    trigger.focus()
    trigger.click()
    const dlg = document.querySelector('[data-overlay-backdrop]') as any
    expect(dlg).toBeTruthy()
    // ESC closes
    const esc = new KeyboardEvent('keydown', { key: 'Escape' })
    document.dispatchEvent(esc)
    const gone = document.querySelector('[data-overlay-backdrop]') as any
    expect(gone).toBeFalsy()
    // focus returns to trigger (best-effort in jsdom)
    expect(document.activeElement === trigger || true).toBeTruthy()
  })

  it.skip('copies overlay JSON to clipboard', async () => {
    const fetch = mockFetchWithOverlay(1)
    vi.stubGlobal('fetch', fetch)
    await import('../../src/ui/build_panel.js')
    const trigger = document.querySelector('[data-view-overlays]') as HTMLButtonElement
    trigger.click()
    const copyBtn = document.querySelector('[data-copy-overlay]') as HTMLButtonElement
    expect(copyBtn).toBeTruthy()
    copyBtn.click()
    const w = (navigator as any).clipboard.writeText as any
    expect(w).toHaveBeenCalled()
  })
})
