import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, getByRole, queryByRole } from '@testing-library/dom'

function mountBaseDOM() {
  document.body.innerHTML = `
    <section class="build-panel" id="build-panel">
      <div class="build-grid">
        <div id="parity-card">
          <div>02 <-> 14: <strong data-parity-02-14>-</strong></div>
          <div>11 <-> 02: <strong data-parity-11-02>-</strong></div>
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

async function waitForSelector(sel: string, timeoutMs = 1000): Promise<Element | null> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const el = document.querySelector(sel);
    if (el) return el;
    await new Promise(r => setTimeout(r, 10));
  }
  return null;
}

describe('overlay summary UI', () => {
  beforeEach(() => {
    mountBaseDOM()
  })

  it('renders View overlays button when items exist; hidden otherwise', async () => {
    vi.stubGlobal('fetch', mockFetchWithOverlay(2))
    const mod = await import('../../src/ui/build_panel.js')
    const btn = await waitForSelector('[data-view-overlays]') as HTMLButtonElement
    expect(btn).toBeTruthy()
    // Now force render with empty overlay_summary and verify absence
    mod.renderParityBanner({ timestamp: 'x', outdir: '/tmp', parity: { '02_vs_14': true,'11_vs_02': true,'03_vs_02': true,'17_vs_02': true }, overlay_summary: { applied: false, items: [] } } as any)
    const btn2 = document.querySelector('[data-view-overlays]') as HTMLButtonElement | null
    expect(btn2).toBeFalsy()
  })

  it('opens modal with role="dialog"; aria-modal=true; ESC closes and focus returns', async () => {
    const mod = await import('../../src/ui/build_panel.js')
    // Render banner with overlay items directly
    mod.renderParityBanner({ timestamp: 'x', outdir: '/tmp', parity: { '02_vs_14': true,'11_vs_02': true,'03_vs_02': true,'17_vs_02': true }, overlay_summary: { applied: true, items: [{ id:'ovl-001', name:'persistence_adaptiveness', version:'v1.0', source:'allowlist', allowlisted:true, status:'applied', notes:'ok', actions:['apply:persistence_adaptiveness'] }], rollback: { supported:true, last_action:'none', ts:'x' } } } as any)
    const trigger = await waitForSelector('[data-view-overlays]') as HTMLButtonElement
    expect(trigger).toBeTruthy()
    trigger.focus()
    trigger.click()
    // Modal present
    const dlg = getByRole(document.body, 'dialog') as HTMLElement
    expect(dlg).toBeTruthy()
    expect(dlg.getAttribute('aria-modal')).toBe('true')
    // Focus moves to first focusable (close button) or dialog
    await new Promise(r => setTimeout(r, 0))
    expect(document.activeElement === dlg || (document.activeElement as HTMLElement)?.className.includes('overlay-close')).toBeTruthy()
    // ESC closes and focus returns to the trigger
    fireEvent.keyDown(document, { key: 'Escape' })
    const gone = queryByRole(document.body, 'dialog')
    expect(gone).toBeNull()
    expect(document.activeElement).toBe(trigger)
  })

  it('copies overlay JSON via the footer button', async () => {
    const spy = vi.spyOn(navigator.clipboard, 'writeText')
    const mod = await import('../../src/ui/build_panel.js')
    mod.renderParityBanner({ timestamp: 'x', outdir: '/tmp', parity: { '02_vs_14': true,'11_vs_02': true,'03_vs_02': true,'17_vs_02': true }, overlay_summary: { applied: true, items: [{ id:'ovl-001', name:'persistence_adaptiveness', version:'v1.0', source:'allowlist', allowlisted:true, status:'applied', notes:'ok', actions:['apply:persistence_adaptiveness'] }], rollback: { supported:true, last_action:'none', ts:'x' } } } as any)
    const trigger = await waitForSelector('[data-view-overlays]') as HTMLButtonElement
    trigger.click()
    const copyBtn = await waitForSelector('[data-copy-overlay]') as HTMLButtonElement
    expect(copyBtn).toBeTruthy()
    fireEvent.click(copyBtn)
    expect(spy).toHaveBeenCalled()
    const arg = (spy.mock.calls[0] || [])[0]
    expect(typeof arg).toBe('string')
    const obj = JSON.parse(String(arg))
    expect(obj && typeof obj === 'object').toBeTruthy()
    expect(obj.applied).toBe(true)
    expect(Array.isArray(obj.items)).toBe(true)
  })
})
