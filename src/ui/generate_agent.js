(function(){
  const btn = document.querySelector('[data-generate-agent]');
  if (!btn) { return; }
  const hidden = (name) => document.querySelector('[name="' + name + '"]');
  function ready(){
    const name = (hidden('agent_name')||{}).value || '';
    const nc = (hidden('naics_code')||{}).value || '';
    const fn = (hidden('business_function')||{}).value || '';
    const rc = (hidden('role_code')||{}).value || '';
    const rt = (hidden('role_title')||{}).value || '';
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

    // v1.2 additions
    profile.identity = {
      agent_id: get('identity.agent_id'),
      display_name: get('identity.display_name'),
      owners: (get('identity.owners')||'').split(',').map(s=>s.trim()).filter(Boolean),
      no_impersonation: !!(form.querySelector('[name="identity.no_impersonation"]')?.checked)
    };
    profile.role_profile = {
      archetype: get('role_profile.archetype'),
      role_title: get('role_profile.role_title'),
      role_recipe_ref: get('role_profile.role_recipe_ref'),
      objectives: (get('role_profile.objectives')||'').split(',').map(s=>s.trim()).filter(Boolean)
    };
    profile.sector_profile = {
      sector: get('sector_profile.sector'),
      industry: get('sector_profile.industry'),
      region: (get('sector_profile.region')||'').split(',').map(s=>s.trim()).filter(Boolean),
      languages: (get('sector_profile.languages')||'').split(',').map(s=>s.trim()).filter(Boolean),
      domain_tags: (get('sector_profile.domain_tags')||'').split(',').map(s=>s.trim()).filter(Boolean),
      risk_tier: get('sector_profile.risk_tier'),
      regulatory: (get('sector_profile.regulatory')||'').split(',').map(s=>s.trim()).filter(Boolean)
    };
    let connectors = parseJsonSafe(get('capabilities_tools.tool_connectors_json'));
    if (!Array.isArray(connectors)) connectors = [];
    profile.capabilities_tools = {
      tool_connectors: connectors,
      human_gate: { actions: (get('capabilities_tools.human_gate.actions')||'').split(',').map(s=>s.trim()).filter(Boolean) }
    };
    profile.memory = {
      memory_scopes: (get('memory.memory_scopes')||'').split(',').map(s=>s.trim()).filter(Boolean),
      initial_memory_packs: (get('memory.initial_memory_packs')||'').split(',').map(s=>s.trim()).filter(Boolean),
      optional_packs: (get('memory.optional_packs')||'').split(',').map(s=>s.trim()).filter(Boolean),
      data_sources: (get('memory.data_sources')||'').split(',').map(s=>s.trim()).filter(Boolean),
    };
    profile.governance_eval = {
      risk_register_tags: (get('governance_eval.risk_register_tags')||'').split(',').map(s=>s.trim()).filter(Boolean),
      pii_flags: (get('governance_eval.pii_flags')||'').split(',').map(s=>s.trim()).filter(Boolean),
      classification_default: get('governance_eval.classification_default') || 'confidential',
    };
    // v3 governance / rbac
    profile.governance = {
      rbac: { roles: (get('governance.rbac.roles')||'').split(',').map(s=>s.trim()).filter(Boolean) },
      policy: {
        no_impersonation: !!(form.querySelector('[name="identity.no_impersonation"]')?.checked),
        classification_default: get('governance_eval.classification_default') || 'confidential',
      }
    };
    // v3 persona extras
    profile.persona = Object.assign({}, profile.persona || {}, {
      tone: get('persona.tone') || 'crisp, analytical, executive',
      collaboration_mode: get('persona.collaboration_mode') || 'Solo'
    });
    // Lifecycle & telemetry (v3)
    profile.lifecycle = { stage: get('lifecycle.stage') || 'dev' };
    const rate = parseFloat(get('telemetry.sampling.rate')||'1.0');
    profile.telemetry = {
      sampling: { rate: isNaN(rate) ? 1.0 : rate },
      sinks: (get('telemetry.sinks')||'').split(',').map(s=>s.trim()).filter(Boolean),
      pii_redaction: { strategy: get('telemetry.pii_redaction.strategy') || 'mask' }
    };
    const adv = parseJsonSafe(get('advanced_overrides'));
    if (adv && typeof adv === 'object') {
      profile.advanced_overrides = adv;
      // Shallow merge for now (server will deep-merge defensively)
      for (const [k, v] of Object.entries(adv)) {
        if (profile[k] === undefined) profile[k] = v;
      }
    } else {
      profile.advanced_overrides = {};
    }

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
