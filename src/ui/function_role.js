(function () {
  const picker = document.querySelector('[data-function-role-picker]');
  if (!picker) {
    return;
  }

  const data = (window.__FUNCTION_ROLE_DATA__ || {
    functions: [],
    roles: [],
    functionDefaults: {}
  });

  const functionSelect = picker.querySelector('[data-function-select]');
  const roleSearch = picker.querySelector('[data-role-search]');
  const roleSelect = picker.querySelector('[data-role-select]');
  const preview = picker.querySelector('[data-role-preview]');

  const hiddenFunction = picker.querySelector('[data-hidden-business-function]');
  const hiddenRoleCode = picker.querySelector('[data-hidden-role-code]');
  const hiddenRoleTitle = picker.querySelector('[data-hidden-role-title]');
  const hiddenRoleSeniority = picker.querySelector('[data-hidden-role-seniority]');
  const hiddenRoutingDefaults = picker.querySelector('[data-hidden-routing-defaults]');

  const bootstrapState = window.__FUNCTION_ROLE_STATE__ || {};
  if (hiddenFunction && bootstrapState.business_function) {
    hiddenFunction.value = bootstrapState.business_function;
  }
  if (hiddenRoleCode && bootstrapState.role_code) {
    hiddenRoleCode.value = bootstrapState.role_code;
  }
  if (hiddenRoleTitle && bootstrapState.role_title) {
    hiddenRoleTitle.value = bootstrapState.role_title;
  }
  if (hiddenRoleSeniority && bootstrapState.role_seniority) {
    hiddenRoleSeniority.value = bootstrapState.role_seniority;
  }
  if (hiddenRoutingDefaults && bootstrapState.routing_defaults_json) {
    hiddenRoutingDefaults.value = bootstrapState.routing_defaults_json;
  }

  const baselineDefaults = {
    workflows: [],
    connectors: [],
    report_templates: [],
    autonomy_default: 0.35,
    safety_bias: 0.7,
    kpi_weights: { PRI: 0.4, HAL: 0.3, AUD: 0.3 }
  };

  const roles = Array.isArray(data.roles) ? data.roles : [];
  const functionDefaults = data.functionDefaults || {};

  function populateFunctions() {
    const current = hiddenFunction?.value || '';
    const fragment = document.createDocumentFragment();
    fragment.append(new Option('Select a business function', '', false, false));
    (Array.isArray(data.functions) ? data.functions : []).forEach((fn) => {
      const option = new Option(fn, fn, false, fn === current);
      fragment.append(option);
    });
    functionSelect.innerHTML = '';
    functionSelect.append(fragment);
    if (current) {
      functionSelect.value = current;
    }
  }

  function roleMatchesFunction(role, fn) {
    return role.function && role.function.toLowerCase() === String(fn || '').toLowerCase();
  }

  function roleMatchesQuery(role, query) {
    if (!query) { return true; }
    const haystack = [role.code, role.seniority, ...(role.titles || [])]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    return String(query)
      .toLowerCase()
      .split(/\s+/)
      .filter(Boolean)
      .every((token) => haystack.includes(token));
  }

  function buildRoleOption(role) {
    const primaryTitle = Array.isArray(role.titles) && role.titles.length ? role.titles[0] : '';
    const codeLabel = role.code ? `(${role.code})` : '';
    const label = [primaryTitle, codeLabel].filter(Boolean).join(' ').trim() || role.code || 'Unknown role';
    return new Option(label, role.code);
  }

  function cloneDefaults(source) {
    return {
      workflows: Array.isArray(source?.workflows) ? [...source.workflows] : [],
      connectors: Array.isArray(source?.connectors) ? [...source.connectors] : [],
      report_templates: Array.isArray(source?.report_templates) ? [...source.report_templates] : [],
      autonomy_default: typeof source?.autonomy_default === 'number' ? source.autonomy_default : baselineDefaults.autonomy_default,
      safety_bias: typeof source?.safety_bias === 'number' ? source.safety_bias : baselineDefaults.safety_bias,
      kpi_weights: source?.kpi_weights ? { ...source.kpi_weights } : { ...baselineDefaults.kpi_weights },
    };
  }

  function resolveDefaults(fn, roleCode) {
    // If server provided merged defaults in bootstrap, prefer those
    try {
      const mergedJson = (window.__FUNCTION_ROLE_STATE__ && window.__FUNCTION_ROLE_STATE__.routing_defaults_json) || '';
      if (mergedJson && typeof mergedJson === 'string') {
        const merged = JSON.parse(mergedJson);
        if (merged && typeof merged === 'object') {
          return cloneDefaults(merged);
        }
      }
    } catch (_) {}

    if (roleCode) {
      const role = roles.find((r) => r.code === roleCode);
      if (role && role.defaults) {
        return cloneDefaults(role.defaults);
      }
    }
    const fnDefaults = functionDefaults[fn];
    if (fnDefaults) {
      return cloneDefaults(fnDefaults);
    }
    return cloneDefaults(baselineDefaults);
  }

  function updateHiddenValues(role) {
    const fn = functionSelect.value || '';
    if (hiddenFunction) hiddenFunction.value = fn;
    if (!role) {
      if (hiddenRoleCode) hiddenRoleCode.value = '';
      if (hiddenRoleTitle) hiddenRoleTitle.value = '';
      if (hiddenRoleSeniority) hiddenRoleSeniority.value = '';
      if (hiddenRoutingDefaults) hiddenRoutingDefaults.value = '';
      return;
    }
    if (hiddenRoleCode) hiddenRoleCode.value = role.code;
    const primaryTitle = role.titles && role.titles.length ? role.titles[0] : role.code;
    if (hiddenRoleTitle) hiddenRoleTitle.value = primaryTitle;
    if (hiddenRoleSeniority) hiddenRoleSeniority.value = role.seniority || '';
    const defaults = resolveDefaults(fn, role.code);
    if (hiddenRoutingDefaults) { hiddenRoutingDefaults.value = JSON.stringify(defaults); }
  }

  function renderList(label, items) {
    const heading = document.createElement('h3');
    heading.textContent = label;
    const list = document.createElement('ul');
    list.className = 'function-role__preview-list';
    items.forEach((item) => {
      const li = document.createElement('li');
      li.textContent = item;
      list.append(li);
    });
    preview.append(heading, list);
  }

  function updatePreview(role) {
    preview.innerHTML = '';
    if (!role) {
      const empty = document.createElement('p');
      empty.className = 'function-role__preview-empty';
      empty.textContent = 'Select a role to view default workflows, connectors, and KPIs.';
      preview.append(empty);
      return;
    }

    const defaults = resolveDefaults(functionSelect.value, role.code);
    const title = Array.isArray(role.titles) && role.titles.length ? role.titles[0] : role.code;

    const heading = document.createElement('h3');
    heading.textContent = title || role.code || 'Selected role';
    preview.append(heading);

    if (defaults.workflows.length) { renderList('Workflows', defaults.workflows); }
    if (defaults.connectors.length) { renderList('Connectors', defaults.connectors); }
    if (defaults.report_templates.length) { renderList('Report Templates', defaults.report_templates); }

    const metrics = document.createElement('p');
    const autonomy = typeof defaults.autonomy_default === 'number' ? Math.round(defaults.autonomy_default * 100) : null;
    const safety = typeof defaults.safety_bias === 'number' ? Math.round(defaults.safety_bias * 100) : null;
    const kpi = defaults.kpi_weights || {};
    const pri = typeof kpi.PRI === 'number' ? Math.round(kpi.PRI * 100) : null;
    const hal = typeof kpi.HAL === 'number' ? Math.round(kpi.HAL * 100) : null;
    const aud = typeof kpi.AUD === 'number' ? Math.round(kpi.AUD * 100) : null;
    metrics.innerHTML = [
      `Autonomy default: ${autonomy !== null ? autonomy + '%' : 'N/A'}`,
      `Safety bias: ${safety !== null ? safety + '%' : 'N/A'}`,
      `KPI weights - PRI ${pri !== null ? pri + '%' : 'N/A'}, HAL ${hal !== null ? hal + '%'}, AUD ${aud !== null ? aud + '%'} `
    ].join(' | ');
    preview.append(metrics);
  }

  function dispatchEvent(name, detail) {
    picker.dispatchEvent(new CustomEvent(name, { detail, bubbles: true }));
  }

  function fetchRole(code) {
    if (!code) return null;
    return roles.find((r) => r.code === code) || null;
  }

  function updateRoleOptions() {
    const fn = functionSelect.value;
    const query = roleSearch.value.trim();
    const filtered = roles
      .filter((role) => roleMatchesFunction(role, fn))
      .filter((role) => roleMatchesQuery(role, query))
      .sort((a, b) => {
        const aLabel = (a.titles?.[0] || a.code).toLowerCase();
        const bLabel = (b.titles?.[0] || b.code).toLowerCase();
        return aLabel.localeCompare(bLabel);
      });

    roleSelect.innerHTML = '';
    if (!fn) {
      roleSelect.append(new Option('Select a role', '', true, true));
      roleSelect.disabled = true;
      updatePreview(null);
      updateHiddenValues(null);
      return;
    }

    roleSelect.append(new Option(filtered.length ? 'Select a role' : 'No roles match search', '', false, true));
    filtered.forEach((role) => roleSelect.append(buildRoleOption(role)));
    roleSelect.disabled = filtered.length === 0;

    const currentCode = hiddenRoleCode?.value;
    if (currentCode && filtered.some((role) => role.code === currentCode)) {
      roleSelect.value = currentCode;
    }

    updatePreview(fetchRole(roleSelect.value));
  }

  function handleFunctionChange() {
    if (hiddenFunction) hiddenFunction.value = functionSelect.value || '';
    if (hiddenRoutingDefaults) hiddenRoutingDefaults.value = '';
    if (hiddenRoleCode) hiddenRoleCode.value = '';
    if (hiddenRoleTitle) hiddenRoleTitle.value = '';
    if (hiddenRoleSeniority) hiddenRoleSeniority.value = '';
    roleSelect.value = '';
    dispatchEvent('business:functionChanged', { value: functionSelect.value });
    updateRoleOptions();
  }

  function handleRoleChange() {
    const role = fetchRole(roleSelect.value);
    updateHiddenValues(role);
    updatePreview(role);
    dispatchEvent('role:changed', { value: role ? role.code : '', role });
  }

  function initialLoad() {
    populateFunctions();
    if (hiddenFunction && hiddenFunction.value) {
      functionSelect.value = hiddenFunction.value;
    }
    updateRoleOptions();
    const initialRole = fetchRole(hiddenRoleCode?.value || '');
    if (initialRole) {
      roleSelect.value = initialRole.code;
      updateHiddenValues(initialRole);
      updatePreview(initialRole);
    }
  }

  functionSelect.addEventListener('change', handleFunctionChange);
  roleSearch.addEventListener('input', updateRoleOptions);
  roleSelect.addEventListener('change', handleRoleChange);

  initialLoad();
})();
