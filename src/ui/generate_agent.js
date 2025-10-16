(function(){
  const btn = document.querySelector('[data-generate-agent]');
  if (!btn) { return; }
  const hidden = (name) => document.querySelector('[name="' + name + '"]');
  function ready(){
    const nc = (hidden('naics_code')||{}).value || '';
    const rc = (hidden('role_code')||{}).value || '';
    const rt = (hidden('role_title')||{}).value || '';
    return nc && (rc || rt);
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

  function get(name){ const el = form.querySelector(`[name="${name}"]`); return el ? (el.value || '').trim() : ''; }
  function getAll(name){ return Array.from(form.querySelectorAll(`input[name="${name}"]:checked`)).map(i=>i.value); }
  function parseJsonSafe(text){ try { return text ? JSON.parse(text) : null; } catch { return null; } }

  function buildProfile(){
    const profile = {
      agent: {
        name: get('agent_name') || 'Custom Project NEO Agent',
        version: get('agent_version') || '1.0.0',
        persona: get('agent_persona') || '',
        domain: get('domain') || '',
        role: get('role') || ''
      },
      toolsets: {
        selected: getAll('toolsets'),
        custom: (get('custom_toolsets')||'').split(',').map(s=>s.trim()).filter(Boolean)
      },
      attributes: {
        selected: getAll('attributes'),
        custom: (get('custom_attributes')||'').split(',').map(s=>s.trim()).filter(Boolean)
      },
      preferences: {
        sliders: {
          autonomy: Number(get('autonomy')||'50')||50,
          confidence: Number(get('confidence')||'50')||50,
          collaboration: Number(get('collaboration')||'50')||50,
        },
        communication_style: get('communication_style') || '',
        collaboration_mode: get('collaboration_mode') || ''
      },
      notes: get('notes') || ''
    };

    // domain selector
    const domainSel = parseJsonSafe(get('domain_selector'));
    if (domainSel && typeof domainSel === 'object') {
      profile.agent.domain_selector = domainSel;
      profile.domain_selector = domainSel;
    }

    // NAICS
    const naicsCode = get('naics_code');
    if (naicsCode) {
      const lineage = parseJsonSafe(get('naics_lineage_json')) || [];
      const levelRaw = get('naics_level');
      const level = levelRaw ? Number(levelRaw) : null;
      const naicsPayload = { code: naicsCode, title: get('naics_title'), level, lineage };
      profile.naics = naicsPayload;
      profile.classification = profile.classification || {};
      profile.classification.naics = naicsPayload;
    }

    // business function + role
    const fn = get('business_function');
    if (fn) { profile.business_function = fn; profile.agent.business_function = fn; }
    const roleCode = get('role_code');
    const roleTitle = get('role_title');
    const roleSenior = get('role_seniority');
    if (roleCode || roleTitle || roleSenior) {
      profile.role = { code: roleCode, title: roleTitle || roleCode, seniority: roleSenior, function: fn || profile.agent.role };
    }

    const routingJson = parseJsonSafe(get('routing_defaults_json'));
    if (routingJson && typeof routingJson === 'object') {
      profile.routing_defaults = routingJson;
    }

    const functionCategory = get('function_category');
    if (functionCategory) { profile.function_category = functionCategory; profile.agent.function_category = functionCategory; }
    const specialties = parseJsonSafe(get('function_specialties_json'));
    if (Array.isArray(specialties)) { profile.function_specialties = specialties.map(String); }

    // LinkedIn
    const linkedinUrl = get('linkedin_url');
    if (linkedinUrl) { profile.linkedin = { url: linkedinUrl }; }

    return profile;
  }

  async function submitProfile(){
    const profile = buildProfile();
    btn.setAttribute('disabled','');
    btn.textContent = 'Generating…';
    try {
      const res = await fetch('/api/agent/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ profile }) });
      const text = await res.text();
      const json = (()=>{ try { return JSON.parse(text) } catch { return null } })();
      if (res.ok && json && json.status === 'ok') {
        alert('Agent repo generation started. Check output in the app logs.');
      } else {
        alert('Generation failed: ' + (json && json.issues ? json.issues.join('; ') : res.status + ' ' + text));
      }
    } catch (err) {
      alert('Generation error: ' + err);
    } finally {
      btn.textContent = 'Generate Agent Repo';
      // keep disabled state logic to gating script
      document.dispatchEvent(new Event('input', { bubbles: true }));
    }
  }

  btn.addEventListener('click', (e) => { e.preventDefault(); submitProfile(); });
})();
