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
  const p0214 = document.querySelector('[data-parity-02-14]');
  const p1102 = document.querySelector('[data-parity-11-02]');
  if (outdirInput) outdirInput.value = data?.outdir || '';
  setText('[data-file-count]', data?.file_count || 0);
  setBoolBadge(p0214, Boolean(data?.parity?.['02_vs_14']));
  setBoolBadge(p1102, Boolean(data?.parity?.['11_vs_02']));
  renderIntegrity('[data-errors-list]', '[data-errors-count]', data?.integrity_errors || []);
  renderIntegrity('[data-warnings-list]', '[data-warnings-count]', data?.warnings || []);
}

function bindPanel() {
  const buildBtn = document.querySelector('[data-build-repo]');
  const copyBtn = document.querySelector('[data-copy-outdir]');
  const p0214 = document.querySelector('[data-parity-02-14]');
  const p1102 = document.querySelector('[data-parity-11-02]');

  if (copyBtn) {
    copyBtn.addEventListener('click', () => {
      const outdirInput = document.querySelector('[data-outdir]');
      if (outdirInput && outdirInput.value) copyToClipboard(outdirInput.value);
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
      const outdirInput = document.querySelector('[data-outdir]');
      if (outdirInput) outdirInput.value = last.outdir || '';
      setText('[data-file-count]', last.file_count || 0);
      setBoolBadge(p0214, Boolean(last?.parity?.['02_vs_14']));
      setBoolBadge(p1102, Boolean(last?.parity?.['11_vs_02']));
      renderIntegrity('[data-errors-list]', '[data-errors-count]', last.integrity_errors || []);
      renderIntegrity('[data-warnings-list]', '[data-warnings-count]', last.warnings || []);
    }
  } catch {}
  bindPanel();
}

// Auto-init when included in the page
if (typeof document !== 'undefined' && typeof window !== 'undefined') {
  try { init(); } catch {}
}
