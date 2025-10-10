/** @jest-environment jsdom */

jest.useFakeTimers();

describe('NAICS search debounce', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div class="naics-selector" data-naics-selector>
        <input data-naics-search />
        <div data-naics-results></div>
        <div data-naics-cascade></div>
        <div data-naics-breadcrumb></div>
        <button type="button" data-naics-confirm disabled>Confirm</button>
      </div>
      <input type="hidden" name="naics_code" />
      <input type="hidden" name="naics_title" />
      <input type="hidden" name="naics_level" />
      <input type="hidden" name="naics_lineage_json" />
    `;
    // @ts-ignore
    global.fetch = jest.fn((url) => {
      if (String(url).endsWith('/api/naics/roots')) return Promise.resolve({ ok:true, json:()=>Promise.resolve({status:'ok', items:[]})});
      if (String(url).includes('/api/naics/search')) return Promise.resolve({ ok:true, json:()=>Promise.resolve({status:'ok', items:[]})});
      return Promise.resolve({ ok:true, json:()=>Promise.resolve({status:'ok'})});
    });
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    require('../../src/ui/domain_bundle.js');
  });

  test('coalesces fast keystrokes into one request', () => {
    const input = document.querySelector('[data-naics-search]') as HTMLInputElement;
    input.value = 'ma'; input.dispatchEvent(new Event('input'));
    input.value = 'man'; input.dispatchEvent(new Event('input'));
    input.value = 'manu'; input.dispatchEvent(new Event('input'));
    // advance less than debounce
    jest.advanceTimersByTime(200);
    // no request yet
    expect((global.fetch as any).mock.calls.filter((c:any)=>String(c[0]).includes('/api/naics/search')).length).toBe(0);
    // advance beyond debounce window
    jest.advanceTimersByTime(150);
    // exactly one request fired
    expect((global.fetch as any).mock.calls.filter((c:any)=>String(c[0]).includes('/api/naics/search')).length).toBe(1);
  });
});
