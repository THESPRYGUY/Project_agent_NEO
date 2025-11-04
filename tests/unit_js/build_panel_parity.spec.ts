import { beforeEach, describe, expect, test } from 'vitest';

import { applyBuildToDom } from '../../src/ui/build_panel.js';

describe('build_panel parity rendering', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="output-card"><div></div></div>
      <input data-outdir value="" />
      <div id="parity-card">
        <div class="parity-row"><strong data-parity-02-14></strong></div>
        <div class="parity-row"><strong data-parity-11-02></strong></div>
      </div>
      <div data-errors-count></div>
      <ul data-errors-list></ul>
      <div data-warnings-count></div>
      <ul data-warnings-list></ul>
    `;
  });

  test('applies parity badges and tooltips for failing packs', () => {
    applyBuildToDom({
      outdir: '/tmp/out',
      file_count: 2,
      parity: { '02_vs_14': true, '11_vs_02': false },
      parity_deltas: {
        '11': { gating: { got: 0.5, expected: 0.75 } },
      },
      integrity_errors: ['missing schema'],
      warnings: ['regenerate overlays'],
    });

    const ok = document.querySelector('[data-parity-02-14]');
    const bad = document.querySelector('[data-parity-11-02]');
    expect(ok?.classList.contains('status-ok')).toBe(true);
    expect(bad?.classList.contains('status-bad')).toBe(true);

    const tooltip = document.querySelector('[data-parity-tooltip="11-02"]');
    expect(tooltip).not.toBeNull();
    expect(tooltip?.textContent).toContain('gating');

    const errorsCount = document.querySelector('[data-errors-count]');
    expect(errorsCount?.textContent).toBe('(1)');
    const errorsList = document.querySelectorAll('[data-errors-list] li');
    expect(errorsList).toHaveLength(1);

    const infoButton = document.querySelector('[data-parity-info]');
    expect(infoButton).not.toBeNull();
  });
});
