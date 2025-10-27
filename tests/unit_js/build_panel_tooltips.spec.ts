import { describe, it, expect, beforeEach, vi } from 'vitest'

function setupDOM() {
  document.body.innerHTML = `
    <div id="parity-card">
      <strong data-parity-02-14>-</strong>
      <strong data-parity-11-02>-</strong>
    </div>
  `
}

describe('build_panel tooltips', () => {
  beforeEach(() => {
    setupDOM()
  })

  it.skip('adds info icon and toggles tooltip with keyboard', async () => {
    const mod = await import('../../src/ui/build_panel.js')
    const sample = {
      outdir: '/tmp/x',
      file_count: 20,
      parity: { '02_vs_14': false, '11_vs_02': true, '03_vs_02': true, '17_vs_02': true },
      parity_deltas: [{ pack: '14', key: 'PRI_min', got: 0.94, expected: 0.95 }],
      integrity_errors: [],
    } as any
    mod.applyBuildToDom(sample)
    // Ensure tooltip rendering pass executed
    mod.renderParityBanner({ timestamp: '2025-01-02T03:04:05Z', outdir: '/tmp/x', parity: sample.parity } as any)
    const info = document.querySelector('[data-parity-info]') as HTMLButtonElement | null
    expect(!!info).toBe(true)
    // toggle open
    info!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    const tip = document.querySelector('[data-parity-tooltip="14-02"]') as HTMLElement | null
    expect(!!tip).toBe(true)
    expect(tip!.hidden).toBe(false)
    // ESC closes
    info!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    expect(tip!.hidden).toBe(true)
  })
})
