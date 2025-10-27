import { describe, it, expect, beforeEach, vi } from 'vitest'

function setupDOM() {
  document.body.innerHTML = `
    <div id="build-panel"></div>
  `
}

describe('overlay modal', () => {
  beforeEach(() => {
    setupDOM()
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn() } })
  })

  it('renders button and opens/closes modal with copy', async () => {
    const mod = await import('../../src/ui/build_panel.js')
    const sample = {
      timestamp: '2025-01-02T03:04:05Z',
      outdir: '/work/AGT/20250102T030405Z',
      parity: { '02_vs_14': false, '11_vs_02': true, '03_vs_02': true, '17_vs_02': true },
      overlay_summary: { applied: true, items: [{ name: 'persistence', version: 'v1', status: 'ok', allowlisted: true, notes: 'n/a' }] },
    } as any
    mod.renderParityBanner(sample)
    const viewBtn = document.querySelector('[data-view-overlays]') as HTMLButtonElement | null
    expect(!!viewBtn).toBe(true)
    viewBtn!.click()
    const backdrop = document.querySelector('[data-overlay-backdrop]') as HTMLElement | null
    expect(!!backdrop).toBe(true)
    const copyBtn = backdrop!.querySelector('[data-copy-overlay]') as HTMLButtonElement | null
    expect(!!copyBtn).toBe(true)
    copyBtn!.click()
    expect(navigator.clipboard.writeText).toHaveBeenCalled()
    // Close via footer button
    const close = backdrop!.querySelector('[data-close-overlay]') as HTMLButtonElement | null
    expect(!!close).toBe(true)
    close!.click()
  })
})

