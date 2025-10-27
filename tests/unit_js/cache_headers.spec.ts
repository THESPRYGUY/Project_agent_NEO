import { describe, it, expect, beforeEach, vi } from 'vitest'

function setupDOM() {
  document.body.innerHTML = `
    <div id="build-panel"></div>
  `
}

describe('cache headers on last-build', () => {
  beforeEach(() => {
    setupDOM()
  })

  it('calls fetch with cache: no-store', async () => {
    const fetchMock = vi.fn(async (url: string, init?: any) => {
      if (url === '/health') return new Response(JSON.stringify({ build_tag: 'v3.0', app_version: '1.2.3', pid: 1, repo_output_dir: '/tmp/out' }), { status: 200 })
      if (url === '/last-build') return new Response('', { status: 204, headers: { 'Cache-Control': 'no-store' } })
      return new Response('notfound', { status: 404 })
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.resetModules()
    await import('../../src/ui/build_panel.js')
    await new Promise(r => setTimeout(r, 0))
    const calls = fetchMock.mock.calls.filter((c: any[]) => c[0] === '/last-build')
    expect(calls.length).toBe(1)
    const init = calls[0][1] || {}
    expect(init.cache).toBe('no-store')
  })
})
