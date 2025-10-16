(function(){
  const button = document.querySelector('[data-generate-agent]');
  if (!button) {
    return;
  }

  const personaInput = document.querySelector('[data-persona-input]');
  const hiddenNaicsCode = document.querySelector('input[name="naics_code"]');
  const hiddenNaicsTitle = document.querySelector('input[name="naics_title"]');
  const hiddenNaicsLevel = document.querySelector('input[name="naics_level"]');
  const hiddenNaicsLineage = document.querySelector('input[name="naics_lineage_json"]');
  const hiddenBusinessFunction = document.querySelector('[data-hidden-business-function]');
  const hiddenRoleCode = document.querySelector('[data-hidden-role-code]');
  const hiddenRoleTitle = document.querySelector('[data-hidden-role-title]');
  const hiddenRoleSeniority = document.querySelector('[data-hidden-role-seniority]');
  const hiddenRoutingDefaults = document.querySelector('[data-hidden-routing-defaults]');

  let evaluateTimer = null;

  function parseLineage(raw) {
    if (!raw) {
      return [];
    }
    try {
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.map(function(node){
        if (typeof node === 'string') {
          return { code: node };
        }
        return node || {};
      }) : [];
    } catch (err) {
      console.warn('generate_agent: failed to parse lineage', err);
      return [];
    }
  }

  function parseNumber(raw) {
    const value = Number.parseInt(raw, 10);
    return Number.isFinite(value) ? value : undefined;
  }

  function parseJSON(raw) {
    if (!raw) {
      return {};
    }
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (err) {
      console.warn('generate_agent: failed to parse routing defaults', err);
      return {};
    }
  }

  function collectState() {
    return {
      mbti: personaInput ? String(personaInput.value || '').trim() : '',
      naics: {
        code: hiddenNaicsCode ? String(hiddenNaicsCode.value || '').trim() : '',
        title: hiddenNaicsTitle ? String(hiddenNaicsTitle.value || '').trim() : '',
        level: parseNumber(hiddenNaicsLevel ? hiddenNaicsLevel.value : undefined),
        lineage: parseLineage(hiddenNaicsLineage ? hiddenNaicsLineage.value : undefined)
      },
      businessFunction: hiddenBusinessFunction ? String(hiddenBusinessFunction.value || '').trim() : '',
      role: {
        code: hiddenRoleCode ? String(hiddenRoleCode.value || '').trim() : '',
        title: hiddenRoleTitle ? String(hiddenRoleTitle.value || '').trim() : '',
        seniority: hiddenRoleSeniority ? String(hiddenRoleSeniority.value || '').trim() : ''
      },
      routingDefaults: parseJSON(hiddenRoutingDefaults ? hiddenRoutingDefaults.value : undefined)
    };
  }

  function isReady(state) {
    if (!state.mbti) return false;
    if (!state.naics.code) return false;
    if (!state.businessFunction) return false;
    if (!state.role.code) return false;
    if (!state.role.title) return false;
    if (!state.routingDefaults || Object.keys(state.routingDefaults).length === 0) return false;
    return true;
  }

  function evaluateButton() {
    const state = collectState();
    button.disabled = !isReady(state);
  }

  function scheduleEvaluate() {
    if (evaluateTimer) {
      clearTimeout(evaluateTimer);
    }
    evaluateTimer = setTimeout(evaluateButton, 0);
  }

  function handleClick(event) {
    const state = collectState();
    if (!isReady(state)) {
      event.preventDefault();
      return;
    }
    const payload = {
      profile: {
        mbti: state.mbti,
        business_function: state.businessFunction,
        role: {
          code: state.role.code,
          title: state.role.title,
          seniority: state.role.seniority,
          function: state.businessFunction
        },
        routing_defaults: state.routingDefaults,
        naics: {
          code: state.naics.code,
          title: state.naics.title,
          level: state.naics.level,
          lineage: state.naics.lineage
        }
      },
      options: {}
    };
    fetch('/api/agent/generate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    }).catch(function(err){
      console.error('generate_agent: request failed', err);
    });
  }

  function attachListeners() {
    var inputs = [
      personaInput,
      hiddenNaicsCode,
      hiddenNaicsTitle,
      hiddenNaicsLevel,
      hiddenNaicsLineage,
      hiddenBusinessFunction,
      hiddenRoleCode,
      hiddenRoleTitle,
      hiddenRoleSeniority,
      hiddenRoutingDefaults
    ].filter(Boolean);

    inputs.forEach(function(el){
      el.addEventListener('input', scheduleEvaluate);
      el.addEventListener('change', scheduleEvaluate);
    });
  }

  button.addEventListener('click', handleClick);
  attachListeners();
  scheduleEvaluate();

  var api = {
    populateState: function(state) {
      state = state || {};
      if (personaInput && state.mbti) personaInput.value = state.mbti;
      if (hiddenNaicsCode && state.naics && state.naics.code) hiddenNaicsCode.value = state.naics.code;
      if (hiddenNaicsTitle && state.naics && state.naics.title) hiddenNaicsTitle.value = state.naics.title;
      if (hiddenNaicsLevel && state.naics && state.naics.level != null) hiddenNaicsLevel.value = String(state.naics.level);
      if (hiddenNaicsLineage && state.naics && state.naics.lineage) hiddenNaicsLineage.value = JSON.stringify(state.naics.lineage);
      if (hiddenBusinessFunction && state.businessFunction) hiddenBusinessFunction.value = state.businessFunction;
      if (hiddenRoleCode && state.role && state.role.code) hiddenRoleCode.value = state.role.code;
      if (hiddenRoleTitle && state.role && state.role.title) hiddenRoleTitle.value = state.role.title;
      if (hiddenRoleSeniority && state.role && state.role.seniority) hiddenRoleSeniority.value = state.role.seniority;
      if (hiddenRoutingDefaults && state.routingDefaults) hiddenRoutingDefaults.value = JSON.stringify(state.routingDefaults);
      scheduleEvaluate();
    },
    collectState: collectState
  };

  if (!window.__GENERATE_AGENT__) {
    window.__GENERATE_AGENT__ = api;
  }
})();
