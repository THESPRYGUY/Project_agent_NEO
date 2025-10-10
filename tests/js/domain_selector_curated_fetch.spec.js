const { JSDOM } = require('jsdom');

// Basic test to ensure dynamic curated list fetch populates options.

describe('DomainSelector dynamic curated fetch', () => {
  let originalFetch;

  beforeEach(() => {
    originalFetch = global.fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  function setupDom() {
    const dom = new JSDOM(`<!DOCTYPE html><div id="domain-selector" data-domain-selector hidden>
      <select data-top-level><option value="" disabled selected>Select a domain group</option></select>
      <select data-subdomain disabled><option value="" disabled selected>Select a subdomain</option></select>
      <input data-tag-input />
      <div data-tags></div>
      <div data-naics-block hidden><input data-naics-code /><div data-naics-hint></div></div>
    </div>`);
    global.window = dom.window;
    global.document = dom.window.document;
    global.CustomEvent = dom.window.CustomEvent;
    return dom;
  }

  test('populates top-level options from fetch', async () => {
    const dom = setupDom();
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok', curated: { 'Strategic Functions': ['Workflow Orchestration'], 'Support Domains': ['Reporting & Publishing'] }})
    });
    const mod = require('../../src/ui/domain_selector.js');
    mod.DomainSelector.mount('#domain-selector');
    // allow microtasks
    await new Promise(r => setTimeout(r, 10));
    const opts = Array.from(dom.window.document.querySelector('[data-top-level]').querySelectorAll('option'));
    const values = opts.map(o => o.value);
    expect(values).toContain('Strategic Functions');
    expect(values).toContain('Support Domains');
  });

  test('fallback if fetch fails', async () => {
    const dom = setupDom();
    global.fetch = jest.fn().mockRejectedValue(new Error('net'));
    const mod = require('../../src/ui/domain_selector.js');
    mod.DomainSelector.mount('#domain-selector');
    await new Promise(r => setTimeout(r, 10));
    const opts = Array.from(dom.window.document.querySelector('[data-top-level]').querySelectorAll('option'));
    const values = opts.map(o => o.value);
    expect(values).toContain('Strategic Functions');
  });
});
