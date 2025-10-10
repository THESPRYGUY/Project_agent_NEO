const { JSDOM } = require('jsdom');

describe('DomainSelector hidden field reset', () => {
  beforeEach(() => {
    const dom = new JSDOM('<!doctype html><html><body>' +
      '<input type="hidden" name="domain_selector" />' +
      '<div id="domain-selector" data-domain-selector hidden>' +
      '<select data-top-level><option value="" disabled selected>Select a domain group</option></select>' +
      '<select data-subdomain disabled><option value="" disabled selected>Select a subdomain</option></select>' +
      '<input data-tag-input />' +
      '<div data-tags></div>' +
      '<div data-naics-block hidden><input data-naics-code /><div data-naics-hint></div></div>' +
      '</div></body></html>', { pretendToBeVisual: true });
    global.window = dom.window;
    global.document = dom.window.document;
    global.CustomEvent = dom.window.CustomEvent;
    // mock curated fetch
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok', curated: { 'Strategic Functions': ['Workflow Orchestration'] } }) });
    delete require.cache[require.resolve('../../src/ui/domain_selector.js')];
    this.DomainSelector = require('../../src/ui/domain_selector.js').DomainSelector;
  });

  afterEach(() => {
    delete global.window;
    delete global.document;
    delete global.CustomEvent;
    delete global.fetch;
  });

  test('clears hidden field when selection becomes incomplete', async () => {
    const comp = this.DomainSelector.mount('#domain-selector');
    await new Promise(r => setTimeout(r, 10));
    const root = document.querySelector('#domain-selector');
    const top = root.querySelector('[data-top-level]');
    const sub = root.querySelector('[data-subdomain]');
    const hidden = document.querySelector('input[name="domain_selector"]');

    top.value = 'Strategic Functions';
    top.dispatchEvent(new window.Event('change'));
    sub.value = 'Workflow Orchestration';
    sub.dispatchEvent(new window.Event('change'));
    expect(hidden.value).toContain('Strategic Functions');

    // Reset top-level to blank
    top.value = '';
    top.dispatchEvent(new window.Event('change'));
    expect(hidden.value).toBe('');
  });
});
