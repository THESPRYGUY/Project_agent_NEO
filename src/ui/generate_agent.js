(function(){
  const btn = document.querySelector('[data-generate-agent]');
  if (!btn) { return; }
  const hidden = (name) => document.querySelector('[name="' + name + '"]');
  function ready(){
    const name = (hidden('agent_name')||{}).value || '';
    const nc = (hidden('naics_code')||{}).value || '';
    const fn = (hidden('business_function')||{}).value || (document.querySelector('[data-function-select]')?.value || '');
    const rc = (hidden('role_code')||{}).value || (document.querySelector('[data-role-select]')?.value || '');
    const rt = (hidden('role_title')||{}).value || (document.querySelector('[data-role-select]')?.selectedOptions?.[0]?.text || '');
    return Boolean(name && nc && fn && (rc || rt));
  }
  function update(){
    if (ready()) { btn.removeAttribute('disabled'); }
    else { btn.setAttribute('disabled',''); }
  }
  // React to common input changes and custom function/role events
  document.addEventListener('change', update, true);
  document.addEventListener('input', update, true);
  document.addEventListener('business:functionChanged', update, true);
  document.addEventListener('role:changed', update, true);
  // Initial state
  update();
})();
(function(){
  const btn = document.querySelector('[data-generate-agent]');
  const form = document.querySelector('form');
  if (!btn || !form) { return; }

  function buildFormBody(){
    const fd = new FormData(form);
    const objectivesInput = form.querySelector('[name="objectives_raw"]');
    if (objectivesInput) {
      const raw = objectivesInput.value || '';
      const lines = raw.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
      fd.delete('objectives');
      lines.forEach((line) => fd.append('objectives', line));
    }
    return new URLSearchParams(fd).toString();
  }

  function fallbackSubmit(){
    const formEl = document.querySelector('form');
    if (!formEl) { return; }
    const marker = document.createElement('input');
    marker.type = 'hidden';
    marker.name = '__auto_repo';
    marker.value = '1';
    formEl.appendChild(marker);
    formEl.submit();
  }

  async function submitProfile(){
    const body = buildFormBody();
    btn.setAttribute('disabled','');
    btn.textContent = 'Generating.';
    try {
      const res = await fetch('/api/agent/generate', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body });
      const text = await res.text();
      const json = (()=>{ try { return JSON.parse(text) } catch { return null } })();
      if (res.ok && json && json.status === 'ok') {
        alert('Agent repo generated successfully. Check the generated_repos folder.');
        return;
      }
      if (res.status === 400 && json && json.errors) {
        const errors = Object.values(json.errors).map(String).filter(Boolean).join('; ');
        alert('Generation failed: ' + (errors || 'Validation error'));
        return;
      }
      if (res.status === 404) {
        console.log('API endpoint not found, falling back to form submit');
        fallbackSubmit();
        return;
      }
      alert('Generation failed: ' + (json && json.issues ? json.issues.join('; ') : res.status + ' ' + text));
    } catch (err) {
      console.error('API call failed, attempting form submit fallback:', err);
      fallbackSubmit();
    } finally {
      btn.textContent = 'Generate Agent Repo';
      // keep disabled state logic to gating script
      document.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  btn.addEventListener('click', (e) => { e.preventDefault(); submitProfile(); });
})();
