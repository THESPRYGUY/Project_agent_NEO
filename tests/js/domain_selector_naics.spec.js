const { JSDOM } = require('jsdom');

let DomainSelector;
let dom;

describe('DomainSelector NAICS UI', () => {
  beforeEach(() => {
    dom = new JSDOM('<!doctype html><html><body></body></html>', { pretendToBeVisual: true, url: 'http://localhost/' });
    global.window = dom.window;
    global.document = dom.window.document;
    global.CustomEvent = dom.window.CustomEvent;
    global.Node = dom.window.Node;

    // Simple fetch mock for NAICS code lookup
    global.fetch = (url) => {
      if (url.includes('/api/naics/code/541611')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok', entry: { code: '541611', title: 'Administrative Management and General Management Consulting Services', level: 6 } }) });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({ status: 'not_found' }) });
    };

    delete require.cache[require.resolve('../../src/ui/domain_selector.js')];
    DomainSelector = require('../../src/ui/domain_selector.js').DomainSelector;
  });

  afterEach(() => {
    dom.window.close();
    delete global.window;
    delete global.document;
    delete global.CustomEvent;
    delete global.Node;
    delete global.fetch;
  });

  test('shows NAICS input for Sector Domains and emits code', async () => {
    document.body.innerHTML = [
      '<div id="domain-selector" data-domain-selector hidden>',
      '  <label><select data-top-level><option value="" disabled selected>Select a domain group</option></select></label>',
      '  <label><select data-subdomain disabled><option value="" disabled selected>Select a subdomain</option></select></label>',
      '  <label><input data-tag-input type="text" /></label>',
      '  <div data-naics-block hidden><label>NAICS Code <input type="text" data-naics-code maxlength="6" /></label><div data-naics-hint></div></div>',
      '  <div data-tags></div>',
      '</div>'
    ].join('');

    const root = document.querySelector('#domain-selector');
    const events = [];
    root.addEventListener('domain:changed', (e) => { events.push(e.detail); });

    // Mock curated domains fetch first call, NAICS code lookup handled by existing conditional
    const originalFetch = global.fetch;
    global.fetch = (url) => {
      if (url === '/api/domains/curated') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok', curated: { 'Sector Domains': ['Energy & Infrastructure'] } }) });
      }
      return originalFetch(url);
    };
    DomainSelector.mount('#domain-selector');
    // allow curated fetch to resolve
    await new Promise(r => setTimeout(r, 10));

    const topLevel = root.querySelector('[data-top-level]');
    const subdomain = root.querySelector('[data-subdomain]');
    const naicsBlock = root.querySelector('[data-naics-block]');
    const naicsInput = root.querySelector('[data-naics-code]');

    // Select Sector Domains
    topLevel.value = 'Sector Domains';
    topLevel.dispatchEvent(new dom.window.Event('change'));
  expect(naicsBlock.hidden).toBe(false);

    // Populate subdomain options now present
    subdomain.value = 'Energy & Infrastructure';
    subdomain.dispatchEvent(new dom.window.Event('change'));

    // Enter NAICS code (triggers debounce -> we await a bit)
    naicsInput.value = '541611';
    naicsInput.dispatchEvent(new dom.window.Event('input'));

    await new Promise(r => setTimeout(r, 400));
    const last = events[events.length - 1];
    expect(last.naics).toEqual({ code: '541611' });
  });
});
