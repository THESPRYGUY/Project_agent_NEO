import { describe, it, expect, beforeEach, vi } from 'vitest'

function setupDOM() {
  document.body.innerHTML = `
    <div id="build-panel"></div>
    <div id="parity-card">
      <strong data-parity-02-14>-</strong>
      <strong data-parity-11-02>-</strong>
    </div>
    <div id="output-card"><div></div></div>
    <input data-outdir />
  `
}

describe('build_panel no last-build', () => {
  beforeEach(() => {
    setupDOM()
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn() } })
    const ss = new Map<string, string>()
    vi.stubGlobal('sessionStorage', {
      getItem: (k: string) => ss.get(k) || null,
      setItem: (k: string, v: string) => { ss.set(k, v) },
      removeItem: (k: string) => { ss.delete(k) },
      clear: () => { ss.clear() },
    })
  })

  it('does not render banner and hides ZIP when 204', async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url === '/health') return new Response(JSON.stringify({ build_tag: 'v3.0', app_version: '1.2.3', pid: 1, repo_output_dir: '/tmp/out' }), { status: 200 })
      if (url === '/last-build') return new Response('', { status: 204, headers: { 'Cache-Control': 'no-store' } })
      return new Response('notfound', { status: 404 })
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.resetModules()
    await import('../../src/ui/build_panel.js')
    await new Promise(r => setTimeout(r, 0))
    const banner = document.querySelector('[data-last-build-banner]')
    expect(banner).toBeNull()
    const zipBtn = document.querySelector('[data-download-zip]') as HTMLAnchorElement | null
    // No last-build means banner absent; zip button may not be created yet
    if (zipBtn) {
      expect(zipBtn.hidden).toBe(true)
    }
  })
})
