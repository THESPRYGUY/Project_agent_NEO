const { JSDOM } = require('jsdom');

// Helper to mount the component in a JSDOM environment mimicking existing tests
function buildDom() {
  const html = `<!DOCTYPE html><html><body>
  <form>
    <input type="hidden" name="domain_selector" />
    <div id="ds" data-domain-selector hidden>
      <label>TL<select data-top-level><option value="" disabled selected>Select</option></select></label>
      <label>SD<select data-subdomain disabled><option value="" disabled selected>Select</option></select></label>
      <label>Tags<input data-tag-input /></label>
      <div data-naics-block hidden>
        <label>NAICS<input data-naics-code maxlength="6" /></label>
        <div class="ds-naics-hint" data-naics-hint aria-live="polite" role="status"></div>
      </div>
      <div data-tags aria-live="polite"></div>
    </div>
  </form>`;
  const dom = new JSDOM(html, { url: 'http://localhost' });
  global.window = dom.window;
  global.document = dom.window.document;
  global.CustomEvent = dom.window.CustomEvent;
  return dom;
}

describe('domain_selector NAICS abort stale lookup', () => {
  let originalFetch;
  beforeEach(() => {
    originalFetch = global.fetch;
  });
  afterEach(() => {
    global.fetch = originalFetch;
    delete global.window;
    delete global.document;
  });

  test('stale NAICS response does not overwrite newer hint', async () => {
    jest.useFakeTimers();
    const dom = buildDom();
    // Prepare mock fetch: first call = curated domains; subsequent calls captured for NAICS lookups
    let naicsResolvers = [];
    global.fetch = jest.fn()
      // curated domains fetch
      .mockImplementationOnce(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok', curated: { 'Sector Domains': ['Energy & Infrastructure'] } }) }))
      // subsequent NAICS lookups
      .mockImplementation(() => new Promise(res => { naicsResolvers.push(res); }));
    const { DomainSelector } = require('../../src/ui/domain_selector.js');

  await DomainSelector.mount('#ds');
    const top = document.querySelector('[data-top-level]');
    const sub = document.querySelector('[data-subdomain]');

    // After bootstrap, insert option manually if needed
    top.insertAdjacentHTML('beforeend', '<option value="Sector Domains">Sector Domains</option>');
    top.value = 'Sector Domains';
    top.dispatchEvent(new dom.window.Event('change'));

    sub.insertAdjacentHTML('beforeend', '<option value="Energy & Infrastructure">Energy & Infrastructure</option>');
    sub.value = 'Energy & Infrastructure';
    sub.dispatchEvent(new dom.window.Event('change'));

    const input = document.querySelector('[data-naics-code]');
    const hint = document.querySelector('[data-naics-hint]');

  // Type first code, let debounce fire -> first fetch (token1)
  input.value = '54161';
  input.dispatchEvent(new dom.window.Event('input'));
  jest.advanceTimersByTime(350); // triggers first lookup
  await Promise.resolve(); await Promise.resolve();
  // Type second code quickly after first network request queued -> second fetch (token2)
  input.value = '541611';
  input.dispatchEvent(new dom.window.Event('input'));
  jest.advanceTimersByTime(350); // triggers second lookup
  await Promise.resolve(); await Promise.resolve();
  // Now we should have two resolvers
  expect(naicsResolvers.length).toBe(2);
  // Resolve second (newer) first
  const newerResponse = { ok: true, json: () => Promise.resolve({ status: 'ok', entry: { title: 'Administrative Management', level: 6 } }) };
  naicsResolvers[1](newerResponse);
    async function flush() { for (let i=0;i<8;i++) { await Promise.resolve(); } }
    // Wait until hint reflects newer response
    for (let tries=0; tries<5; tries++) {
      await flush();
      if (/Administrative Management/.test(hint.textContent)) break;
    }
    expect(hint.textContent).toMatch(/Administrative Management/);
  // Resolve older -> should not overwrite
  const olderResponse = { ok: true, json: () => Promise.resolve({ status: 'ok', entry: { title: 'Old Title', level: 5 } }) };
  naicsResolvers[0](olderResponse);
  await Promise.resolve(); await Promise.resolve();
  // Still should show newer text
  expect(hint.textContent).toMatch(/Administrative Management/);
    jest.useRealTimers();
  });
});
