import { describe, it, expect, beforeEach, vi } from 'vitest'

// Minimal DOM scaffold used by build_panel.js
function mountDOM() {
  document.body.innerHTML = `
    <section class="build-panel" id="build-panel">
      <div class="build-grid">
        <div id="parity-card">
          <div>02 <-> 14: <strong data-parity-02-14>-</strong></div>
          <div>11 <-> 02: <strong data-parity-11-02>-</strong></div>
        </div>
        <div id="integrity-card">
          <div>Files: <strong data-file-count>0</strong></div>
          <details><ul data-errors-list></ul></details>
          <details><ul data-warnings-list></ul></details>
        </div>
        <div id="output-card"><div>
          <input data-outdir />
          <a href="#" data-open-outdir>Open</a>
          <button data-copy-outdir>Copy Path</button>
        </div></div>
      </div>
    </section>
  `
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

describe('build_panel UI', () => {
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

  it('renders Last-Build banner and ZIP button', async () => {
    const { fn, calls } = mockFetchSequence()
    vi.stubGlobal('fetch', fn)
    await import('../../src/ui/build_panel.js')
    // ZIP button exists and uses encoded outdir
    const zip = document.querySelector('[data-download-zip]') as HTMLAnchorElement
    expect(zip).toBeTruthy()
    expect(zip.hidden).toBe(false)
    expect(zip.href).toContain(encodeURIComponent('/work/AGT/20250102T030405Z'))
    // Last-build banner exists
    const banner = document.querySelector('[data-last-build-banner]')
    expect(banner).toBeTruthy()
    // fetch called with no-store for last-build
    const call = calls.find(c => String(c[0]).endsWith('/last-build'))
    expect(call).toBeTruthy()
    expect((call[1]||{}).cache).toBe('no-store')
  })

  it('shows tooltip when parity=false and renders deltas', async () => {
    const { fn } = mockFetchSequence()
    vi.stubGlobal('fetch', fn)
    await import('../../src/ui/build_panel.js')
    // after init, parity 02_vs_14 is false; info button should exist
    const info = document.querySelector('[data-parity-info]') as HTMLButtonElement
    expect(info).toBeTruthy()
    // aria-expanded toggles
    expect(info.getAttribute('aria-expanded')).toBe('false')
    info.click()
    const tip = document.querySelector('[data-parity-tooltip="14-02"]') as HTMLElement
    expect(tip).toBeTruthy()
    expect(info.getAttribute('aria-expanded')).toBe('true')
    expect(tip.hidden).toBe(false)
    // ESC closes
    const esc = new KeyboardEvent('keydown', { key: 'Escape' })
    document.dispatchEvent(esc)
    expect(info.getAttribute('aria-expanded')).toBe('false')
    expect(tip.hidden).toBe(true)
    // Content includes deltas
    expect(tip.innerHTML).toContain('PRI_min')
  })
})
