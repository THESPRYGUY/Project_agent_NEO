import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen } from '@testing-library/dom'

function setupDOM() {
  document.body.innerHTML = `
    <div id="app">
      <div id="build-panel"></div>
      <div id="parity-card">
        <strong data-parity-02-14>-</strong>
        <strong data-parity-11-02>-</strong>
      </div>
      <div id="output-card"><div></div></div>
      <input data-outdir />
    </div>
  `
}

describe('build_panel banner', () => {
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

  it('renders banner, copies path, and sets ZIP link', async () => {
    const sample = {
      timestamp: '2025-01-02T03:04:05Z',
      outdir: '/work/AGT/20250102T030405Z',
      file_count: 20,
      parity: { '02_vs_14': true, '11_vs_02': true, '03_vs_02': true, '17_vs_02': true },
      overlays_applied: false,
      integrity_errors: [],
    }
    const fetchMock = vi.fn(async (url: string) => {
      if (url === '/health') return new Response(JSON.stringify({ build_tag: 'v3.0', app_version: '1.2.3', pid: 1, repo_output_dir: '/tmp/out' }), { status: 200 })
      if (url === '/last-build') return new Response(JSON.stringify(sample), { status: 200, headers: { 'Cache-Control': 'no-store' } })
      return new Response('notfound', { status: 404 })
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.resetModules()
    const mod = await import('../../src/ui/build_panel.js')
    await new Promise(r => setTimeout(r, 0))
    // Banner should appear
    const banner = document.querySelector('[data-last-build-banner]') as HTMLElement | null
    expect(!!banner).toBe(true)
    // Copy Path
    const copyBtn = banner!.querySelector('[data-copy-last]') as HTMLButtonElement | null
    expect(!!copyBtn).toBe(true)
    copyBtn!.click()
    expect(navigator.clipboard.writeText).toHaveBeenCalled()
    // ZIP href encoded
    const a = banner!.querySelector('[data-last-zip]') as HTMLAnchorElement | null
    expect(!!a).toBe(true)
    expect(a!.href).toContain(encodeURIComponent(sample.outdir))
  })
})
