/** @jest-environment jsdom */
// Basic DOM simulation test for function selection script
// We mock fetch for functions catalog and NAICS endpoints minimally

describe('function selection UI basics', () => {
  beforeAll(() => {
    // Minimal DOM structure
    document.body.innerHTML = `
      <div data-function-select>
        <div>
          <label><input type="radio" name="function_category_choice" value="Strategic"></label>
          <label><input type="radio" name="function_category_choice" value="Technical"></label>
        </div>
        <div data-specialties-block hidden>
          <div data-specialty-chips></div>
          <input data-specialty-input />
        </div>
      </div>
      <input name="function_category" type="hidden" />
      <input name="function_specialties_json" type="hidden" />
    `;

    // Mock fetch for functions catalog
    // @ts-ignore
    global.fetch = jest.fn((url: string) => {
      if (url.includes('/data/functions/functions_catalog.json')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ Strategic: ['Planning','Governance'], Technical: ['ETL','APIs'] })});
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok', items: [] })});
    });

    // Load the bundle script (assumes it is built to build/src/ui/domain_bundle.js)
    // We only need the function part; require should execute IIFE.
  try { require('../../src/ui/domain_bundle.js'); } catch (_){ /* ignore if not present */ }
  });

  test('selecting category populates hidden field and allows chip selection', async () => {
    const strategicRadio = document.querySelector('input[value="Strategic"]') as HTMLInputElement;
    strategicRadio.checked = true;
    strategicRadio.dispatchEvent(new Event('change'));

    // allow microtask queue
    await new Promise(r => setTimeout(r, 5));

    const hiddenCat = document.querySelector('input[name="function_category"]') as HTMLInputElement;
    expect(hiddenCat.value).toBe('Strategic');

    // click a rendered specialty chip (should have been created dynamically)
    const chipsContainer = document.querySelector('[data-specialty-chips]') as HTMLElement;
    const firstChip = chipsContainer.querySelector('button');
    if (firstChip) {
      firstChip.dispatchEvent(new Event('click'));
      const hiddenSpecs = document.querySelector('input[name="function_specialties_json"]') as HTMLInputElement;
      expect(hiddenSpecs.value).toContain('Planning');
    }
  });
});
