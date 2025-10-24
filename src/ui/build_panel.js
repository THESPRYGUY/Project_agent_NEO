// Build & Verify Panel logic (ES module)

export async function getHealth() {
  const res = await fetch('/health', { method: 'GET' });
  const text = await res.text();
  let data = null;
  try { data = JSON.parse(text); } catch { data = null; }
  if (!res.ok || !data) {
    throw new Error(`health_failed:${res.status}`);
  }
  return data;
}

export async function getLastBuild() {
  try {
    const res = await fetch('/last-build', { method: 'GET', cache: 'no-store' });
    if (res.status === 204) return null;
    const text = await res.text();
    return JSON.parse(text);
  } catch { return null; }
}

export function persistLastBuild(summary) {
  try { sessionStorage.setItem('NEO_LAST_BUILD', JSON.stringify(summary)); } catch {}
}

export function readLastBuild() {
  try {
    const raw = sessionStorage.getItem('NEO_LAST_BUILD');
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export async function buildRepo() {
  const res = await fetch('/build', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  const traceId = res.headers.get('x-request-id') || '';
  const text = await res.text();
  let data = null;
  try { data = JSON.parse(text); } catch { data = null; }
  if (!res.ok || !data) {
    const error = new Error(`build_failed:${res.status}`);
    error.traceId = traceId;
    throw error;
  }
  persistLastBuild(data);
  return { data, traceId };
}

function setText(sel, value) {
  const el = document.querySelector(sel);
  if (el) { el.textContent = value == null ? '' : String(value); }
}

function setBoolBadge(el, ok) {
  if (!el) return;
  el.textContent = ok ? '✅' : '❌';
  if (el.classList && typeof el.classList.remove === 'function') {
    el.classList.remove('status-ok','status-bad');
    el.classList.add(ok ? 'status-ok' : 'status-bad');
  }
}

function renderIntegrity(listSel, countSel, items) {
  const list = document.querySelector(listSel);
  const count = document.querySelector(countSel);
  if (count) count.textContent = `(${(items||[]).length})`;
  if (!list) return;
  list.innerHTML = '';
  (items || []).forEach((msg) => {
    const li = document.createElement('li');
    li.textContent = String(msg);
    list.appendChild(li);
  });
}

function copyToClipboard(text) {
  try { navigator.clipboard.writeText(text); } catch {}
}

export function applyBuildToDom(data) {
  const outdirInput = document.querySelector('[data-outdir]');
  const zipBtn = ensureZipButton();
  const p0214 = document.querySelector('[data-parity-02-14]');
  const p1102 = document.querySelector('[data-parity-11-02]');
  const p0302 = document.querySelector('[data-parity-03-02]');
  const p1702 = document.querySelector('[data-parity-17-02]');
  // Ensure new parity badges exist in DOM for 03↔02 and 17↔02
  try {
    const card = document.getElementById('parity-card');
    if (card) {
      if (!p0302) {
        const d = document.createElement('div');
        d.innerHTML = '03 ↔ 02: <strong data-parity-03-02 title="03 activation vs 02 targets">-</strong>';
        card.appendChild(d);
      }
      if (!p1702) {
        const d2 = document.createElement('div');
        d2.innerHTML = '17 ↔ 02: <strong data-parity-17-02 title="17 activation vs 02 targets">-</strong>';
        card.appendChild(d2);
      }
    }
  } catch {}
  if (outdirInput) outdirInput.value = data?.outdir || '';
  if (zipBtn) {
    zipBtn.href = data?.outdir ? ('/build/zip?outdir=' + encodeURIComponent(data.outdir)) : '#';
    zipBtn.hidden = !Boolean(data?.outdir);
  }
  setText('[data-file-count]', data?.file_count || 0);
  setBoolBadge(p0214, Boolean(data?.parity?.['02_vs_14']));
  setBoolBadge(p1102, Boolean(data?.parity?.['11_vs_02']));
  setBoolBadge(p0302, Boolean(data?.parity?.['03_vs_02']));
  setBoolBadge(p1702, Boolean(data?.parity?.['17_vs_02']));
  renderIntegrity('[data-errors-list]', '[data-errors-count]', data?.integrity_errors || []);
  renderIntegrity('[data-warnings-list]', '[data-warnings-count]', data?.warnings || []);
  renderParityTooltips(data);
}

function ensureZipButton() {
  let btn = document.querySelector('[data-download-zip]');
  if (!btn) {
    const card = document.getElementById('output-card');
    if (card) {
      btn = document.createElement('a');
      btn.textContent = 'Download ZIP';
      btn.href = '#';
      btn.setAttribute('data-download-zip', '1');
      btn.setAttribute('download', 'repo.zip');
      btn.className = 'build-panel__btn';
      btn.hidden = true;
      const container = card.querySelector('div');
      (container || card).appendChild(btn);
    }
  }
  return btn;
}

function deltasToList(deltas) {
  const items = [];
  if (!deltas) return items;
  if (Array.isArray(deltas)) return deltas.map(x => ({ pack: String(x.pack||''), key: String(x.key||''), got: x.got, expected: x.expected }));
  try {
    for (const pack of Object.keys(deltas)) {
      const kv = deltas[pack] || {};
      for (const k of Object.keys(kv)) {
        const pair = kv[k];
        const got = Array.isArray(pair) ? pair[0] : (pair && pair.got);
        const expected = Array.isArray(pair) ? pair[1] : (pair && pair.expected);
        items.push({ pack, key: k, got, expected });
      }
    }
  } catch {}
  return items;
}

function renderParityTooltips(data) {
  const parity = (data && data.parity) || {};
  const deltas = deltasToList(data && data.parity_deltas);
  const map = {
    '02_vs_14': { el: document.querySelector('[data-parity-02-14]'), pack: '14' },
    '11_vs_02': { el: document.querySelector('[data-parity-11-02]'), pack: '11' },
    '03_vs_02': { el: document.querySelector('[data-parity-03-02]'), pack: '03' },
    '17_vs_02': { el: document.querySelector('[data-parity-17-02]'), pack: '17' },
  };
  for (const k of Object.keys(map)) {
    const ok = Boolean(parity[k]);
    const target = map[k].el;
    if (!target) continue;
    const old = target.parentElement && target.parentElement.querySelector('[data-parity-info]');
    if (old) old.remove();
    if (ok) continue;
    const info = document.createElement('button');
    info.type = 'button';
    info.textContent = 'i';
    info.className = 'info-btn';
    try { info.setAttribute('aria-label', 'Show parity deltas'); } catch {}
    try { info.setAttribute('data-parity-info', '1'); } catch {}
    try { info.setAttribute('role', 'button'); } catch {}
    try { info.setAttribute('aria-expanded', 'false'); } catch {}
    info.tabIndex = 0;
    const pack = map[k].pack;
    const relevant = deltas.filter(d => String(d.pack) === String(pack));
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    try { tooltip.setAttribute('role', 'tooltip'); } catch {}
    tooltip.hidden = true;
    const tipId = 'parity-tip-' + pack;
    try { tooltip.setAttribute('id', tipId); } catch {}
    try { tooltip.setAttribute('data-parity-tooltip', pack + '-02'); } catch {}
    tooltip.innerHTML = relevant.map(d => `${pack} ${d.key} — ${Number(d.got).toFixed(3)} → ${Number(d.expected).toFixed(3)}`).join('<br>');
    try { info.setAttribute('aria-controls', tipId); } catch {}
    function setOpen(open) {
      tooltip.hidden = !open;
      try { info.setAttribute('aria-expanded', open ? 'true' : 'false'); } catch {}
    }
    try { info.addEventListener('click', () => { setOpen(tooltip.hidden); }); } catch {}
    try {
      info.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpen(tooltip.hidden); }
        if (e.key === 'Escape') { e.preventDefault(); setOpen(false); }
      });
    } catch {}
    try { document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { setOpen(false); } }); } catch {}
    const parent = target.parentElement || target;
    try { if (parent && typeof parent.appendChild === 'function') parent.appendChild(info); } catch {}
    try { if (parent && typeof parent.appendChild === 'function') parent.appendChild(tooltip); } catch {}
  }
}

function bindPanel() {
  const buildBtn = document.querySelector('[data-build-repo]');
  const copyBtn = document.querySelector('[data-copy-outdir]');
  const openLink = document.querySelector('[data-open-outdir]');
  const p0214 = document.querySelector('[data-parity-02-14]');
  const p1102 = document.querySelector('[data-parity-11-02]');
  const p0302 = document.querySelector('[data-parity-03-02]');
  const p1702 = document.querySelector('[data-parity-17-02]');

  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const outdirInput = document.querySelector('[data-outdir]');
      if (outdirInput && outdirInput.value) copyToClipboard(outdirInput.value);
    });
  }
  if (openLink) {
    openLink.addEventListener('click', (e) => {
      e.preventDefault();
      const outdirInput = document.querySelector('[data-outdir]');
      const p = outdirInput && outdirInput.value;
      if (p) {
        // Browsers typically block file:// but keep link visible with tooltip
        try { openLink.href = 'file://' + p; openLink.title = p; window.open(openLink.href, '_blank'); } catch { /* noop */ }
      }
    });
  }

  if (buildBtn) {
    buildBtn.addEventListener('click', async () => {
      buildBtn.setAttribute('disabled','');
      buildBtn.textContent = 'Building…';
      try {
        const { data } = await buildRepo();
        applyBuildToDom(data);
      } catch (err) {
        const trace = (err && err.traceId) ? ` (trace ${err.traceId})` : '';
        try { alert('Build failed' + trace); } catch {}
      } finally {
        buildBtn.removeAttribute('disabled');
        buildBtn.textContent = 'Build Repo';
      }
    });
  }
}

async function init() {
  // Health chip
  try {
    const h = await getHealth();
    setText('[data-intake-schema]', h.build_tag || 'v3.0');
    setText('[data-app-version]', h.app_version || '0.0.0');
    setText('[data-pid]', h.pid || '');
    setText('[data-repo-output-dir]', h.repo_output_dir || '');
  } catch {}
  // Last build
  try {
    const last = readLastBuild();
    if (last) {
      const p0214 = document.querySelector('[data-parity-02-14]');
      const p1102 = document.querySelector('[data-parity-11-02]');
      const p0302 = document.querySelector('[data-parity-03-02]');
      const p1702 = document.querySelector('[data-parity-17-02]');
      const outdirInput = document.querySelector('[data-outdir]');
      if (outdirInput) outdirInput.value = last.outdir || '';
      ensureZipButton();
      const zipBtn = document.querySelector('[data-download-zip]');
      if (zipBtn) { zipBtn.href = last?.outdir ? ('/build/zip?outdir=' + encodeURIComponent(last.outdir)) : '#'; zipBtn.hidden = !Boolean(last?.outdir); }
      setText('[data-file-count]', last.file_count || 0);
      setBoolBadge(p0214, Boolean(last?.parity?.['02_vs_14']));
      setBoolBadge(p1102, Boolean(last?.parity?.['11_vs_02']));
      setBoolBadge(p0302, Boolean(last?.parity?.['03_vs_02']));
      setBoolBadge(p1702, Boolean(last?.parity?.['17_vs_02']));
      renderIntegrity('[data-errors-list]', '[data-errors-count]', last.integrity_errors || []);
      renderIntegrity('[data-warnings-list]', '[data-warnings-count]', last.warnings || []);
      renderParityBanner(last);
      renderParityTooltips(last);
    }
    const fresh = await getLastBuild();
    if (fresh) {
      persistLastBuild(fresh);
      applyBuildToDom(fresh);
      renderParityBanner(fresh);
    }
  } catch {}
  bindPanel();
}

// Auto-init when included in the page
if (typeof document !== 'undefined' && typeof window !== 'undefined') {
  try { init(); } catch {}
}

export function renderParityBanner(summary) {
  try {
    let banner = document.querySelector('[data-last-build-banner]');
    if (!banner) {
      const panel = document.getElementById('build-panel');
      banner = document.createElement('div');
      banner.setAttribute('data-last-build-banner', '1');
      banner.className = 'last-build-banner';
      if (panel && panel.parentElement) {
        panel.parentElement.insertBefore(banner, panel);
      }
    }
    const ts = String(summary.timestamp || '').replace('T', ' ').replace('Z','Z');
    const allTrue = ['02_vs_14','11_vs_02','03_vs_02','17_vs_02'].every(k => Boolean(summary?.parity?.[k]));
    const outdir = String(summary.outdir || '');
    banner.innerHTML = '' +
      `<div class="banner-row">` +
        `<span class="badge ${allTrue ? 'ok' : 'warn'}" aria-label="Aggregate parity">${allTrue ? 'ALL TRUE' : 'NEEDS REVIEW'}</span>` +
        `<span class="ts">${ts}</span>` +
        `<span class="path mono" title="${outdir}">${outdir}</span>` +
        `<span class="ovl">Overlays: ${summary.overlays_applied ? 'yes' : 'no'}</span>` +
        `<button type="button" class="build-panel__btn" data-copy-last>Copy Path</button>` +
        `<a class="build-panel__btn" data-last-zip href="${outdir ? ('/build/zip?outdir=' + encodeURIComponent(outdir)) : '#'}" ${outdir ? '' : 'hidden'}>Download ZIP</a>` +
      `</div>`;
    const copy = banner.querySelector('[data-copy-last]');
    const a = banner.querySelector('[data-last-zip]');
    if (copy) copy.addEventListener('click', () => outdir && copyToClipboard(outdir));
    if (a) a.hidden = !Boolean(outdir);
  } catch {}
}
