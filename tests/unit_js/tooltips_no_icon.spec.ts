import { describe, it, expect } from 'vitest'

describe('tooltips branch coverage', () => {
  it('does not render info icon when parity=true', async () => {
    document.body.innerHTML = `<div id="parity-card"><strong data-parity-02-14>-</strong><strong data-parity-11-02>-</strong></div>`
    const mod = await import('../../src/ui/build_panel.js')
    const sample = { outdir: '/tmp/x', file_count: 20, parity: { '02_vs_14': true, '11_vs_02': true, '03_vs_02': true, '17_vs_02': true }, integrity_errors: [] } as any
    mod.applyBuildToDom(sample)
    const info = document.querySelector('[data-parity-info]')
    expect(info).toBeNull()
  })
})

