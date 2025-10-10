/** @jest-environment jsdom */

describe('NAICS cascade rendering and lineage', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div class="naics-selector" data-naics-selector>
        <input data-naics-search />
        <div data-naics-results></div>
        <div data-naics-cascade>
          <label>Level 2 <select data-naics-level2 disabled></select></label>
          <label>Level 3 <select data-naics-level3 disabled></select></label>
          <label>Level 4 <select data-naics-level4 disabled></select></label>
          <label>Level 5 <select data-naics-level5 disabled></select></label>
          <label>Level 6 <select data-naics-level6 disabled></select></label>
        </div>
        <div data-naics-breadcrumb></div>
        <button type="button" data-naics-confirm disabled>Confirm</button>
      </div>
      <input type="hidden" name="naics_code" />
      <input type="hidden" name="naics_title" />
      <input type="hidden" name="naics_level" />
      <input type="hidden" name="naics_lineage_json" />
    `;

    // Mock fetch for cascade endpoints
    const roots = { status:'ok', items:[
      { code:'31', title:'Manufacturing', level:2 },
    ] };
    const children: Record<string, any> = {
      '31': { status:'ok', parent:'31', items:[ { code:'311', title:'Food Manufacturing', level:3 } ] },
      '311': { status:'ok', parent:'311', items:[ { code:'3111', title:'Animal Food Mfg', level:4 } ] },
      '3111': { status:'ok', parent:'3111', items:[ { code:'31111', title:'Animal (except Poultry) Food Mfg', level:5 } ] },
      '31111': { status:'ok', parent:'31111', items:[ { code:'311111', title:'Dog and Cat Food Manufacturing', level:6 } ] },
    };
    const codeMap: Record<string, any> = {
      '31': { status:'ok', entry:{ code:'31', title:'Manufacturing', level:2, parents:[] } },
      '311': { status:'ok', entry:{ code:'311', title:'Food Manufacturing', level:3, parents:[{code:'31', title:'Manufacturing', level:2}] } },
      '3111': { status:'ok', entry:{ code:'3111', title:'Animal Food Mfg', level:4, parents:[{code:'31', title:'Manufacturing', level:2},{code:'311', title:'Food Manufacturing', level:3}] } },
      '31111': { status:'ok', entry:{ code:'31111', title:'Animal (except Poultry) Food Mfg', level:5, parents:[{code:'31', title:'Manufacturing', level:2},{code:'311', title:'Food Manufacturing', level:3},{code:'3111', title:'Animal Food Mfg', level:4}] } },
      '311111': { status:'ok', entry:{ code:'311111', title:'Dog and Cat Food Manufacturing', level:6, parents:[{code:'31', title:'Manufacturing', level:2},{code:'311', title:'Food Manufacturing', level:3},{code:'3111', title:'Animal Food Mfg', level:4},{code:'31111', title:'Animal (except Poultry) Food Mfg', level:5}] } },
    };
    // @ts-ignore
    global.fetch = jest.fn((rawUrl: string) => {
      const url = String(rawUrl);
      if (url.endsWith('/api/naics/roots')) return Promise.resolve({ ok:true, json:()=>Promise.resolve(roots)});
      if (url.includes('/api/naics/children/')){
        // Support level-targeted queries: /children/<code>?level=3|4|5|6
        const parts = url.split('/');
        const last = parts[parts.length-1];
        const [codeOnly, query] = last.split('?');
        const level = query && query.includes('level=') ? Number((query.split('level=')[1]||'').split('&')[0]) : undefined;
        if (codeOnly === '31' && level === 3){
          return Promise.resolve({ ok:true, json:()=>Promise.resolve({ status:'ok', parent:'31', items:[ { code:'311', title:'Food Manufacturing', level:3 } ] })});
        }
        if (codeOnly === '311' && level === 4){
          return Promise.resolve({ ok:true, json:()=>Promise.resolve({ status:'ok', parent:'311', items:[ { code:'3111', title:'Animal Food Mfg', level:4 } ] })});
        }
        if (codeOnly === '3111' && level === 5){
          return Promise.resolve({ ok:true, json:()=>Promise.resolve({ status:'ok', parent:'3111', items:[ { code:'31111', title:'Animal (except Poultry) Food Mfg', level:5 } ] })});
        }
        if (codeOnly === '31111' && level === 6){
          return Promise.resolve({ ok:true, json:()=>Promise.resolve({ status:'ok', parent:'31111', items:[ { code:'311111', title:'Dog and Cat Food Manufacturing', level:6 } ] })});
        }
        // Fallback to legacy map if present
        return Promise.resolve({ ok:true, json:()=>Promise.resolve(children[codeOnly]||{status:'ok',items:[]})});
      }
      if (url.includes('/api/naics/code/')){
        const k = url.split('/').pop() as string; return Promise.resolve({ ok:true, json:()=>Promise.resolve(codeMap[k])});
      }
      if (url.includes('/api/naics/search')){ return Promise.resolve({ ok:true, json:()=>Promise.resolve({ status:'ok', items:[] })}); }
      return Promise.resolve({ ok:false, json:()=>Promise.resolve({}) });
    });

    // Load bundle
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    require('../../src/ui/domain_bundle.js');
  });

  test('select 2→3→4→5→6 populates lineage and breadcrumbs', async () => {
    // Wait a tick for roots fetch
    await new Promise(r=>setTimeout(r, 1));
    const sel2 = document.querySelector('[data-naics-level2]') as HTMLSelectElement;
    const sel3 = document.querySelector('[data-naics-level3]') as HTMLSelectElement;
    const sel4 = document.querySelector('[data-naics-level4]') as HTMLSelectElement;
    const sel5 = document.querySelector('[data-naics-level5]') as HTMLSelectElement;
    const sel6 = document.querySelector('[data-naics-level6]') as HTMLSelectElement;
    expect(sel2).toBeTruthy(); expect(sel3).toBeTruthy(); expect(sel4).toBeTruthy(); expect(sel5).toBeTruthy(); expect(sel6).toBeTruthy();
    // Level 2 (sector)
    sel2.value = '31'; sel2.dispatchEvent(new Event('change'));
    await new Promise(r=>setTimeout(r, 1));
    // Level 3
    sel3.value = '311'; sel3.dispatchEvent(new Event('change'));
    await new Promise(r=>setTimeout(r, 1));
    // Level 4
    sel4.value = '3111'; sel4.dispatchEvent(new Event('change'));
    await new Promise(r=>setTimeout(r, 1));
    // Level 5
    sel5.value = '31111'; sel5.dispatchEvent(new Event('change'));
    await new Promise(r=>setTimeout(r, 1));
    // Level 6
    sel6.value = '311111'; sel6.dispatchEvent(new Event('change'));
    await new Promise(r=>setTimeout(r, 1));

  // Now commit via Confirm button
  const confirmBtn = document.querySelector('[data-naics-confirm]') as HTMLButtonElement;
  expect(confirmBtn.disabled).toBe(false);
  confirmBtn.click();
  await new Promise(r=>setTimeout(r, 1));

    const hiddenCode = (document.querySelector('input[name="naics_code"]') as HTMLInputElement).value;
    const hiddenLineage = JSON.parse((document.querySelector('input[name="naics_lineage_json"]') as HTMLInputElement).value||'[]');
    const breadcrumb = (document.querySelector('[data-naics-breadcrumb]') as HTMLElement).textContent || '';

  expect(hiddenCode).toBe('311111');
  expect(hiddenLineage.map((n:any)=>n.code)).toEqual(['31','311','3111','31111','311111']);
    expect(breadcrumb).toContain('Manufacturing');
    expect(breadcrumb).toContain('Dog and Cat Food Manufacturing');
  });
});
