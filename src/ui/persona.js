(function () {
  const root = document.querySelector('[data-persona-tabs]');
  if (!root) {
    return;
  }

  const operatorGrid = root.querySelector('[data-operator-grid]');
  const operatorSelection = root.querySelector('[data-operator-selection]');
  const summaryElement = root.querySelector('[data-persona-summary]');
  const suggestButton = root.querySelector('[data-suggest-persona]');
  const acceptButton = root.querySelector('[data-accept-persona]');
  const suggestionScore = root.querySelector('[data-suggestion-score]');
  const suggestionDetails = root.querySelector('[data-suggestion-details]');
  const alternatesContainer = root.querySelector('[data-alternates]');
  const personaInput = document.querySelector('[data-persona-input]');
  const traitsContainer = root.querySelector('[data-persona-traits]');
  const traitsChips = root.querySelector('[data-traits-chips]');
  const traitsMeta = root.querySelector('[data-traits-meta]');
  const copyTraitsButton = root.querySelector('[data-copy-traits]');

const tooltipRoot = document.querySelector('[data-mbti-tooltips="enabled"]');
let tooltipElement = null;
let tooltipData = new Map();
let tooltipActiveButton = null;
let traitsLexicon = {};
let traitsOverlays = {};
let lastRenderedTraits = [];

const TOOLTIP_ID = 'mbti-tooltip';
const AXIS_TRAIT_POOL = {
  EI: {
    E: ['energy_connector', 'engagement_host'],
    I: ['analytical_anchor', 'calm_mediator'],
  },
  SN: {
    S: ['process_anchor', 'precision_advocate'],
    N: ['innovation_scout', 'foresight_planner'],
  },
  TF: {
    T: ['strategic_executor', 'diagnostic_solver'],
    F: ['values_champion', 'people_steward'],
  },
  JP: {
    J: ['decisive_orchestrator', 'quality_guardian'],
    P: ['experience_crafter', 'curiosity_researcher'],
  },
};
const FALLBACK_TRAITS = ['strategic_executor', 'values_champion', 'innovation_scout', 'process_anchor', 'team_mobilizer'];

function ensureTooltipElement() {
  if (!tooltipRoot) {
    return null;
  }
  if (!tooltipElement) {
    tooltipElement = document.getElementById(TOOLTIP_ID);
    if (!tooltipElement) {
      tooltipElement = document.createElement('div');
      tooltipElement.id = TOOLTIP_ID;
      tooltipElement.setAttribute('role', 'tooltip');
      tooltipElement.setAttribute('aria-live', 'polite');
      tooltipElement.hidden = true;
      document.body.appendChild(tooltipElement);
    }
  }
  return tooltipElement;
}

function truncateDescription(input) {
  if (!input) {
    return '';
  }
  return input.length > 180 ? input.slice(0, 177) + '\u2026' : input;
}

function showTooltip(button) {
  if (!tooltipRoot) {
    return;
  }
  const code = (button.getAttribute('data-mbti-code') || button.dataset.mbtiCode || '').toUpperCase();
  if (!code) {
    return;
  }
  const meta = tooltipData.get(code);
  if (!meta) {
    return;
  }
  const tooltip = ensureTooltipElement();
  if (!tooltip) {
    return;
  }
  const name = meta.nickname || meta.name || '';
  const description = truncateDescription(meta.summary || meta.description || '');
  tooltip.innerHTML = '<strong>' + code + '</strong> &#8212; ' + name + '<br>' + description;
  const rect = button.getBoundingClientRect();
  tooltip.style.left = Math.round(window.scrollX + rect.left) + 'px';
  tooltip.style.top = Math.round(window.scrollY + rect.bottom + 8) + 'px';
  tooltip.hidden = false;
  if (tooltipActiveButton && tooltipActiveButton !== button) {
    if (tooltipActiveButton.getAttribute('aria-describedby') === TOOLTIP_ID) {
      tooltipActiveButton.removeAttribute('aria-describedby');
    }
  }
  button.setAttribute('aria-describedby', TOOLTIP_ID);
  tooltipActiveButton = button;
}

function hideTooltip(button) {
  const tooltip = ensureTooltipElement();
  if (!tooltip) {
    return;
  }
  tooltip.hidden = true;
  tooltip.innerHTML = '';
  const target = button || tooltipActiveButton;
  if (target && target.getAttribute('aria-describedby') === TOOLTIP_ID) {
    target.removeAttribute('aria-describedby');
  }
  if (!button || button === tooltipActiveButton) {
    tooltipActiveButton = null;
  }
}

function handleTooltipKeydown(event) {
  if (event.key === 'Escape' || event.key === 'Esc') {
    hideTooltip(event.currentTarget);
  }
}

function bindTooltip(button) {
  if (!tooltipRoot || button.dataset.tooltipBound === '1') {
    return;
  }
  button.dataset.tooltipBound = '1';
  button.addEventListener('mouseenter', function () {
    showTooltip(button);
  });
  button.addEventListener('mouseleave', function () {
    hideTooltip(button);
  });
  button.addEventListener('focus', function () {
    showTooltip(button);
  });
  button.addEventListener('blur', function () {
    hideTooltip(button);
  });
  button.addEventListener('keydown', handleTooltipKeydown);
}

function initialiseTooltips(types) {
  if (!tooltipRoot) {
    return;
  }
  tooltipData = new Map();
  types.forEach(function (entry) {
    if (entry && entry.code) {
      tooltipData.set(String(entry.code).toUpperCase(), entry);
    }
  });
  const tooltip = ensureTooltipElement();
  if (!tooltip) {
    return;
  }
  hideTooltip();
  operatorGrid.querySelectorAll('.persona-mbti').forEach(function (button) {
    bindTooltip(button);
  });
}

  const configUrl = '/api/persona/config';
  const stateUrl = '/api/persona/state';

  let config = null;
  let currentState = {
    operator: null,
    agent: null,
    suggestion: null,
  };

  initialiseTabs();
  fetchConfiguration();
  if (copyTraitsButton) {
    copyTraitsButton.addEventListener('click', (event) => {
      event.preventDefault();
      copyTraitsToClipboard();
    });
  }

  function updatePersonaInput(value) {
    if (personaInput) {
      personaInput.value = value || "";
    }
  }

  function initialiseTabs() {
    const tabs = root.querySelectorAll('.persona-tab');
    const panels = root.querySelectorAll('.persona-panel');

    tabs.forEach((tab) => {

      tab.addEventListener('click', (ev) => { ev.preventDefault(); ev.stopPropagation(); withScrollPreserved(() => activateTab(tab.dataset.tabTarget)); });
      tab.addEventListener('keydown', (event) => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
          return;
        }
        event.preventDefault();
        const ordered = Array.from(tabs);
        const currentIndex = ordered.indexOf(tab);
        let nextIndex = currentIndex;
        if (event.key === 'ArrowRight') {
          nextIndex = (currentIndex + 1) % ordered.length;
        } else if (event.key === 'ArrowLeft') {
          nextIndex = (currentIndex - 1 + ordered.length) % ordered.length;
        } else if (event.key === 'Home') {
          nextIndex = 0;
        } else if (event.key === 'End') {
          nextIndex = ordered.length - 1;
        }
        withScrollPreserved(() => activateTab(ordered[nextIndex].dataset.tabTarget));
        try { ordered[nextIndex].focus({ preventScroll: true }); } catch { ordered[nextIndex].focus(); }
      });
    });

    function activateTab(target) {
      tabs.forEach((tab) => {
        const active = tab.dataset.tabTarget === target;
        tab.classList.toggle('persona-tab--active', active);
        tab.setAttribute('aria-selected', active ? 'true' : 'false');
        tab.setAttribute('tabindex', active ? '0' : '-1');
      });
      panels.forEach((panel) => {
        const shouldShow = panel.id === `persona-panel-${target}`;
        if (shouldShow) {
          panel.removeAttribute('hidden');
        } else {
          panel.setAttribute('hidden', '');
        }
      });
    }
  }

  function roleSelected() {
    const hiddenRole = document.querySelector('[name="role_code"]');
    const hiddenTitle = document.querySelector('[name="role_title"]');
    const code = (hiddenRole && hiddenRole.value) || '';
    const title = (hiddenTitle && hiddenTitle.value) || '';
    return Boolean(code || title);
  }

  function updatePersonaGating() {
    if (suggestButton) {
      suggestButton.disabled = !roleSelected();
    }
    // acceptButton remains governed by suggestion flow
  }

  function fetchConfiguration() {
    fetchJson(configUrl)
      .then((data) => {
        config = data;
        traitsLexicon = data.traits_lexicon || {};
        traitsOverlays = {};
        if (data.traits_overlays && typeof data.traits_overlays === 'object') {
          Object.entries(data.traits_overlays).forEach(([key, value]) => {
            if (Array.isArray(value)) {
              traitsOverlays[String(key).toUpperCase()] = value.map((item) => String(item).trim()).filter(Boolean);
            }
          });
        }
        renderOperatorButtons(data.mbti_types);
        return fetchJson(stateUrl);
      })
      .then((state) => {
        if (state) {
          currentState = Object.assign({}, currentState, state);
          restoreState();
        }
      })
      .catch((error) => {
        console.error('Persona configuration failed to load', error);
        showSummary('Unable to load persona module. Try refreshing after running the validator.');
      });
  }

  function fetchJson(url) {
    return fetch(url, {
      headers: {
        Accept: 'application/json',
      },
    }).then((response) => {
      if (!response.ok) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      return response.json();
    });
  }

  function withScrollPreserved(fn) {
    const x = window.scrollX, y = window.scrollY;
    try { fn(); } finally { requestAnimationFrame(() => window.scrollTo(x, y)); }
  }

  function hashSeed(input) {
    let hash = 0;
    const text = String(input || 'persona-traits');
    for (let i = 0; i < text.length; i += 1) {
      hash = (hash * 1664525 + text.charCodeAt(i)) >>> 0;
    }
    return hash >>> 0;
  }

  function shuffleWithSeed(array, seed) {
    const result = array.slice();
    let state = hashSeed(seed);
    for (let i = result.length - 1; i > 0; i -= 1) {
      state = (state * 1664525 + 1013904223) >>> 0;
      const j = state % (i + 1);
      const tmp = result[i];
      result[i] = result[j];
      result[j] = tmp;
    }
    return result;
  }

  function deriveAxes(code) {
    const upper = String(code || '').toUpperCase();
    const labels = ['EI', 'SN', 'TF', 'JP'];
    return labels.reduce((acc, label, idx) => {
      acc[label] = upper[idx] || '';
      return acc;
    }, {});
  }

  function normaliseTraitKey(key) {
    const tidy = String(key || '').trim();
    if (!tidy) {
      return null;
    }
    return Object.prototype.hasOwnProperty.call(traitsLexicon, tidy) ? tidy : null;
  }

  function currentRoleCode() {
    const input = document.querySelector('[data-hidden-role-code]');
    return input ? input.value : '';
  }

  function currentAgentId() {
    const input = document.querySelector('[name="identity.agent_id"]');
    return input ? input.value : '';
  }

  function composeTraitsForUI(options) {
    const roleKey = options.roleKey ? options.roleKey.toUpperCase() : '';
    const baseTraits = Array.isArray(options.mbtiTraits) ? options.mbtiTraits : [];
    const axes = options.axes || deriveAxes(options.code);
    const priority = [];
    const seen = new Set();

    function addPriority(candidate) {
      const key = normaliseTraitKey(candidate);
      if (key && !seen.has(key)) {
        priority.push(key);
        seen.add(key);
      }
    }

    if (roleKey && Array.isArray(traitsOverlays[roleKey])) {
      traitsOverlays[roleKey].forEach(addPriority);
    }

    baseTraits.forEach(addPriority);

    if (priority.length > 0) {
      return priority.slice(0, 5);
    }

    const fallbackCandidates = [];
    Object.entries(axes || {}).forEach(([axis, letter]) => {
      const pool = AXIS_TRAIT_POOL[axis];
      const mapped = pool ? pool[String(letter).toUpperCase()] : null;
      if (Array.isArray(mapped)) {
        mapped.forEach((candidate) => {
          const key = normaliseTraitKey(candidate);
          if (key && !fallbackCandidates.includes(key)) {
            fallbackCandidates.push(key);
          }
        });
      }
    });

    if (!fallbackCandidates.length) {
      FALLBACK_TRAITS.forEach((candidate) => {
        const key = normaliseTraitKey(candidate);
        if (key && !fallbackCandidates.includes(key)) {
          fallbackCandidates.push(key);
        }
      });
    }

    if (!fallbackCandidates.length) {
      Object.keys(traitsLexicon || {}).forEach((key) => {
        const tidy = normaliseTraitKey(key);
        if (tidy && !fallbackCandidates.includes(tidy)) {
          fallbackCandidates.push(tidy);
        }
      });
    }

    if (!fallbackCandidates.length) {
      return [];
    }

    const seed = options.agentId || options.code || 'persona-traits';
    const ordered = shuffleWithSeed(fallbackCandidates, seed);
    if (ordered.length < 3) {
      const base = fallbackCandidates.length > 0 ? fallbackCandidates : ordered;
      let idx = 0;
      while (ordered.length < 3 && base.length > 0) {
        const key = base[idx % base.length];
        ordered.push(key);
        idx += 1;
      }
    }
    return ordered.slice(0, 5);
  }

  function renderTraits(traits, updatedAt) {
    if (!traitsContainer || !traitsChips || !traitsMeta) {
      return;
    }
    if (!traits || traits.length === 0) {
      traitsChips.innerHTML = '';
      traitsMeta.textContent = '';
      traitsContainer.hidden = true;
      lastRenderedTraits = [];
      return;
    }
    lastRenderedTraits = traits.slice();
    const chipsHtml = traits
      .map((key) => {
        const label = traitsLexicon[key] || key;
        return `<span class="persona-traits__chip" data-trait-key="${key}">${label}</span>`;
      })
      .join('');
    traitsChips.innerHTML = chipsHtml;
    if (updatedAt) {
      const epoch = typeof updatedAt === 'number' ? updatedAt : Date.now();
      const ms = epoch > 10 ** 12 ? epoch : epoch * 1000;
      traitsMeta.textContent = `Last refreshed ${new Date(ms).toLocaleString()}`;
    } else {
      traitsMeta.textContent = '';
    }
    traitsContainer.hidden = false;
  }

  function copyTraitsToClipboard() {
    if (!lastRenderedTraits.length) {
      showSummary('No traits to copy yet.');
      return;
    }
    const text = lastRenderedTraits.map((key) => traitsLexicon[key] || key).join(', ');
    const fallback = () => {
      try {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'absolute';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        showSummary('Traits copied to clipboard.');
      } catch (err) {
        console.error(err);
        showSummary('Unable to copy traits on this browser.');
      }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text)
        .then(() => showSummary('Traits copied to clipboard.'))
        .catch(() => fallback());
    } else {
      fallback();
    }
  }

  function renderOperatorButtons(types) {
    operatorGrid.innerHTML = '';

    types.forEach((entry) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'persona-mbti';
      button.dataset.code = entry.code;
      button.setAttribute('data-mbti-code', entry.code);
      button.setAttribute('aria-pressed', 'false');
      button.innerHTML = `<strong>${entry.code}</strong><span>${entry.nickname}</span>`;
      button.addEventListener('click', (ev) => { ev.preventDefault(); ev.stopPropagation(); withScrollPreserved(() => selectOperator(entry)); });
      button.addEventListener('keydown', (event) => handleOperatorKeydown(event, entry));
      operatorGrid.appendChild(button);
    });

    updatePersonaGating();
    suggestButton.addEventListener('click', (ev) => { ev.preventDefault(); ev.stopPropagation(); withScrollPreserved(handleSuggestPersona); });
    acceptButton.addEventListener('click', (ev) => { ev.preventDefault(); ev.stopPropagation(); withScrollPreserved(persistPersonaSelection); });
    initialiseTooltips(types);
  }

  function handleOperatorKeydown(event, entry) {
    const buttons = Array.from(operatorGrid.querySelectorAll('.persona-mbti'));
    const currentIndex = buttons.findIndex((item) => item.dataset.code === entry.code);
    if (['ArrowRight', 'ArrowDown'].includes(event.key)) {
      event.preventDefault();
      const nxt = buttons[(currentIndex + 1) % buttons.length];
      try { nxt.focus({ preventScroll: true }); } catch { nxt.focus(); }
    } else if (['ArrowLeft', 'ArrowUp'].includes(event.key)) {
      event.preventDefault();
      const prv = buttons[(currentIndex - 1 + buttons.length) % buttons.length];
      try { prv.focus({ preventScroll: true }); } catch { prv.focus(); }
    }
  }

  function selectOperator(entry) {
    currentState.operator = {
      code: entry.code,
      name: entry.name,
      nickname: entry.nickname,
    };
    updateOperatorButtons();
    operatorSelection.textContent = `${entry.code} - ${entry.nickname}`;
    showSummary(`Operator persona set to ${entry.code}. Generate a suggestion for the agent.`);
  }

  function updateOperatorButtons() {
    const selected = currentState.operator ? currentState.operator.code : null;
    operatorGrid.querySelectorAll('.persona-mbti').forEach((button) => {
      const active = button.dataset.code === selected;
      button.dataset.active = active ? 'true' : 'false';
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function handleSuggestPersona() {
    if (!config) {
      showSummary('Persona config not ready yet.');
      return;
    }
    if (!currentState.operator) {
      showSummary('Select an operator MBTI to generate a suggestion.');
      return;
    }
    const preferences = collectPreferences();
    const suggestion = suggestAgentPersona({
      domain: getSelectValue('domain'),
      role: currentRoleCode() || getSelectValue('role'),
      operatorType: currentState.operator.code,
      preferences,
    }, config);

    currentState.suggestion = suggestion;
    renderSuggestion(suggestion);
    acceptButton.disabled = false;
    showSummary(`Suggested ${suggestion.code} persona for the agent. Accept to persist.`);
  }

  function collectPreferences() {
    const autonomy = parseInt(valueOrDefault('autonomy'), 10);
    const confidence = parseInt(valueOrDefault('confidence'), 10);
    const collaboration = parseInt(valueOrDefault('collaboration'), 10);
    return { autonomy, confidence, collaboration };
  }

  function valueOrDefault(name) {
    const input = document.querySelector(`[name="${name}"]`);
    return input ? input.value : '50';
  }

  function getSelectValue(name) {
    const select = document.querySelector(`[name="${name}"]`);
    return select ? select.value : null;
  }

  function renderSuggestion(suggestion) {
    if (!suggestion) {
      suggestionScore.textContent = '';
      suggestionDetails.innerHTML = '';
      alternatesContainer.setAttribute('hidden', '');
      renderTraits([], null);
      return;
    }

    suggestionScore.textContent = `${suggestion.code} - blended score ${suggestion.blendedScore}%`;
    const listItems = suggestion.rationale.map((item) => `<li>${item}</li>`).join('');
    suggestionDetails.innerHTML = `
      <p>Compatibility: <strong>${suggestion.compatibilityScore}%</strong></p>
      <p>Role Fit: <strong>${suggestion.roleFitScore}%</strong></p>
      <ul>${listItems}</ul>
    `;

    const alternatesList = alternatesContainer.querySelector('ul');
    if (suggestion.alternates && suggestion.alternates.length > 0) {
      alternatesList.innerHTML = suggestion.alternates
        .map((alt) => `<li>${alt.code} (${alt.blendedScore}%)</li>`)
        .join('');
      alternatesContainer.removeAttribute('hidden');
    } else {
      alternatesList.innerHTML = '';
      alternatesContainer.setAttribute('hidden', '');
    }
    const entry = config && Array.isArray(config.mbti_types)
      ? config.mbti_types.find((item) => item.code === suggestion.code)
      : null;
    const baseTraits = entry && Array.isArray(entry.suggested_traits) ? entry.suggested_traits : [];
    const traitKeys = Array.isArray(suggestion.traits) && suggestion.traits.length > 0
      ? suggestion.traits
      : composeTraitsForUI({
        code: suggestion.code,
        mbtiTraits: baseTraits,
        roleKey: currentRoleCode(),
        axes: deriveAxes(suggestion.code),
        agentId: currentAgentId(),
      });
    renderTraits(traitKeys, suggestion.updatedAt || currentState.updated_at || Date.now());
    if (currentState.suggestion) {
      currentState.suggestion.traits = traitKeys;
      currentState.suggestion.updatedAt = suggestion.updatedAt || Date.now();
    }
  }

  function persistPersonaSelection() {
    if (!currentState.operator || !currentState.suggestion) {
      showSummary('Generate a suggestion before accepting.');
      return;
    }

    const payload = {
      operator: currentState.operator,
      agent: {
        code: currentState.suggestion.code,
        rationale: currentState.suggestion.rationale,
        compatibility: currentState.suggestion.compatibilityScore,
        role_fit: currentState.suggestion.roleFitScore,
        blended: currentState.suggestion.blendedScore,
      },
      alternates: currentState.suggestion.alternates,
    };
    const roleCode = currentRoleCode();
    const functionInput = document.querySelector('[name="business_function"]');
    const agentId = currentAgentId();
    if (roleCode) {
      payload.agent.role_code = roleCode;
    }
    if (functionInput && functionInput.value) {
      payload.agent.business_function = functionInput.value;
    }
    if (agentId) {
      payload.agent.agent_id = agentId;
    }

    fetch(stateUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to persist persona state');
        }
        return response.json();
      })
      .then((saved) => {
        currentState = Object.assign({}, currentState, saved);
        updatePersonaInput(saved?.agent?.code ?? '');
        const savedTraits = (saved?.persona_details?.suggested_traits)
          || (saved?.agent?.mbti?.suggested_traits)
          || [];
        const suggestion = {
          code: saved?.agent?.code ?? currentState.suggestion.code,
          rationale: saved?.agent?.rationale || currentState.suggestion.rationale,
          compatibilityScore: saved?.agent?.compatibility ?? currentState.suggestion.compatibilityScore,
          roleFitScore: saved?.agent?.role_fit ?? currentState.suggestion.roleFitScore,
          blendedScore: saved?.agent?.blended ?? currentState.suggestion.blendedScore,
          alternates: saved?.alternates || currentState.suggestion.alternates,
          traits: savedTraits,
          updatedAt: saved?.updated_at ? saved.updated_at * 1000 : Date.now(),
        };
        renderSuggestion(suggestion);
        showSummary(`Saved agent persona ${saved.agent?.code ?? ''}. Reload to confirm persistence.`);
      })
      .catch((error) => {
        console.error(error);
        showSummary('Unable to persist persona state. Check the server logs for details.');
      });
  }

  // React to function/role changes to gate suggestion
  document.addEventListener('business:functionChanged', updatePersonaGating, true);
  document.addEventListener('role:changed', updatePersonaGating, true);
  document.addEventListener('change', updatePersonaGating, true);
  document.addEventListener('input', updatePersonaGating, true);

  function restoreState() {
    updatePersonaInput('');
    if (currentState.operator) {
      const match = config.mbti_types.find((entry) => entry.code === currentState.operator.code);
      if (match) {
        operatorSelection.textContent = `${match.code} - ${match.nickname}`;
        updateOperatorButtons();
      }
    }

    if (currentState.agent) {
      const savedTraits = (currentState.persona_details && currentState.persona_details.suggested_traits)
        || (currentState.agent.mbti && currentState.agent.mbti.suggested_traits)
        || [];
      const suggestion = {
        code: currentState.agent.code,
        rationale: currentState.agent.rationale || [],
        compatibilityScore: currentState.agent.compatibility || 0,
        roleFitScore: currentState.agent.role_fit || 0,
        blendedScore: currentState.agent.blended || 0,
        alternates: currentState.alternates || [],
        traits: savedTraits,
        updatedAt: currentState.updated_at ? currentState.updated_at * 1000 : Date.now(),
      };
      renderSuggestion(suggestion);
      acceptButton.disabled = false;
      updatePersonaInput(currentState.agent.code || '');
    }

    if (currentState.updated_at) {
      showSummary(`Persona last saved ${new Date(currentState.updated_at).toLocaleString()}.`);
    }
  }

  function showSummary(message) {
    summaryElement.textContent = message;
  }

  // ---------- Suggestion logic (mirrors TypeScript implementation) ----------
  const AXES = [0, 1, 2, 3];

  function normaliseType(code) {
    if (!code) {
      return '';
    }
    return String(code).toUpperCase().replace(/[^EINFTSPJ]/g, '');
  }

  function compatibilityScoreJS(operator, agent) {
    const op = normaliseType(operator);
    const ag = normaliseType(agent);
    if (op.length !== 4 || ag.length !== 4) {
      return { score: 0, matches: 0, mismatches: 0 };
    }
    let matches = 0;
    let mismatches = 0;
    AXES.forEach((index) => {
      if (op[index] === ag[index]) {
        matches += 1;
      } else {
        mismatches += 1;
      }
    });
    const score = clamp(40 + matches * 15 - mismatches * 5, 20, 100);
    return { score: Math.round(score), matches, mismatches };
  }

  function roleFitScoreJS(domain, role, agent, priors) {
    const ag = normaliseType(agent);
    if (ag.length !== 4) {
      return { score: 0, factors: [] };
    }
    const factors = [];
    let score = 55;
    if (domain && priors[domain]) {
      const domainMap = priors[domain];
      const roleCodes = collectCodes(domainMap[role || '']);
      const defaultCodes = collectCodes(domainMap._default);
      const domainCodes = new Set([...(roleCodes || []), ...(defaultCodes || [])]);
      if (role && roleCodes.includes(ag)) {
        score = 95;
        factors.push(`Strong prior: ${ag} excels for ${role} in ${domain}.`);
      } else if (defaultCodes.includes(ag)) {
        score = 82;
        factors.push(`Domain match: ${ag} is a reliable fit within ${domain}.`);
      } else if (domainCodes.size > 0) {
        score = 68;
        factors.push(`Adjacent fit: ${ag} aligns with neighbouring personas for ${domain}.`);
      } else {
        score = 60;
        factors.push(`No explicit prior for ${domain}; using balanced baseline.`);
      }
    } else {
      score = 60;
      factors.push('Domain not provided; using generic persona baseline.');
    }
    return { score: Math.round(clamp(score, 0, 100)), factors };
  }

  function blendedScoreJS(compatibility, roleFit, preferenceWeight) {
    const weight = clamp(preferenceWeight ?? 0.5, 0, 1);
    const composite = weight * compatibility + (1 - weight) * roleFit;
    return Math.round(clamp(composite, 0, 100));
  }

  function preferenceBiasJS(code, preferences) {
    if (!preferences) {
      return { bonus: 0, notes: [] };
    }
    const upper = normaliseType(code);
    const notes = [];
    let bonus = 0;
    const autonomy = preferences.autonomy ?? 50;
    const collaboration = preferences.collaboration ?? 50;
    const confidence = preferences.confidence ?? 50;

    if (autonomy >= 65 && (upper.includes('I') || upper.includes('P'))) {
      bonus += 4;
      notes.push('High autonomy preference favours independent (I/P) personas.');
    } else if (autonomy <= 40 && upper.includes('E')) {
      bonus += 2;
      notes.push('Lower autonomy leans toward collaborative (E) personas.');
    }

    if (collaboration >= 60 && upper.includes('F')) {
      bonus += 3;
      notes.push('Collaboration slider boosts feeling-oriented personas.');
    } else if (collaboration <= 40 && upper.includes('T')) {
      bonus += 2;
      notes.push('Analytical collaboration preference favours thinking (T) personas.');
    }

    if (confidence >= 65 && upper.includes('J')) {
      bonus += 4;
      notes.push('Confidence preference rewards decisive (J) personas.');
    } else if (confidence <= 40 && upper.includes('P')) {
      bonus += 2;
      notes.push('Discovery-oriented confidence slider gives perceiving (P) personas room.');
    }

    return { bonus, notes };
  }

  function suggestAgentPersona(input, cfg) {
    const priors = cfg.priors_by_domain_role;
    const types = cfg.mbti_types;
    const candidates = deriveCandidatesJS(input.domain, input.role, priors, types);
    const scores = candidates.map((entry) => {
      const compatibility = compatibilityScoreJS(input.operatorType, entry.code);
      const roleFit = roleFitScoreJS(input.domain, input.role, entry.code, priors);
      const preference = preferenceBiasJS(entry.code, input.preferences);
      const composite = blendedScoreJS(
        compatibility.score + preference.bonus,
        roleFit.score,
        input.operatorType ? 0.62 : 0.5,
      );
      return {
        entry,
        compatibility,
        roleFit,
        preference,
        composite,
      };
    });
    scores.sort((a, b) => b.composite - a.composite);
    const best = scores[0];
    const alternates = scores.slice(1, 4).map((candidate) => ({
      code: candidate.entry.code,
      blendedScore: candidate.composite,
    }));

    const rationale = [
      `Compatibility with operator: ${best.compatibility.score}%`,
      ...best.preference.notes,
      ...best.roleFit.factors,
    ];
    const roleCode = currentRoleCode();
    const agentId = currentAgentId();
    const traits = composeTraitsForUI({
      code: best.entry.code,
      mbtiTraits: best.entry.suggested_traits || [],
      roleKey: roleCode,
      axes: deriveAxes(best.entry.code),
      agentId,
    });

    return {
      code: best.entry.code,
      compatibilityScore: best.compatibility.score,
      roleFitScore: best.roleFit.score,
      blendedScore: best.composite,
      rationale,
      alternates,
      traits,
      updatedAt: Date.now(),
    };
  }

  function deriveCandidatesJS(domain, role, priors, types) {
    const uniqueCodes = new Set();
    if (domain && priors[domain]) {
      const domainMap = priors[domain];
      collectCodes(domainMap[role || '']).forEach((code) => uniqueCodes.add(code));
      collectCodes(domainMap._default).forEach((code) => uniqueCodes.add(code));
    }
    if (uniqueCodes.size === 0) {
      types.forEach((entry) => uniqueCodes.add(normaliseType(entry.code)));
    }
    return types.filter((entry) => uniqueCodes.has(normaliseType(entry.code)));
  }

  function collectCodes(codes) {
    return (codes || [])
      .map((code) => normaliseType(code))
      .filter((code) => code.length === 4);
  }

  function clamp(value, lower, upper) {
    return Math.max(lower, Math.min(upper, value));
  }
})();
