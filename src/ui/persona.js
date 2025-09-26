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

  function updatePersonaInput(value) {
    if (personaInput) {
      personaInput.value = value || "";
    }
  }

  function initialiseTabs() {
    const tabs = root.querySelectorAll('.persona-tab');
    const panels = root.querySelectorAll('.persona-panel');

    tabs.forEach((tab) => {
      tab.addEventListener('click', () => activateTab(tab.dataset.tabTarget));
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
        activateTab(ordered[nextIndex].dataset.tabTarget);
        ordered[nextIndex].focus();
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

  function fetchConfiguration() {
    fetchJson(configUrl)
      .then((data) => {
        config = data;
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

  function renderOperatorButtons(types) {
    operatorGrid.innerHTML = '';

    types.forEach((entry) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'persona-mbti';
      button.dataset.code = entry.code;
      button.setAttribute('aria-pressed', 'false');
      button.innerHTML = `<strong>${entry.code}</strong><span>${entry.nickname}</span>`;
      button.addEventListener('click', () => selectOperator(entry));
      button.addEventListener('keydown', (event) => handleOperatorKeydown(event, entry));
      operatorGrid.appendChild(button);
    });

    suggestButton.addEventListener('click', handleSuggestPersona);
    acceptButton.addEventListener('click', persistPersonaSelection);
  }

  function handleOperatorKeydown(event, entry) {
    const buttons = Array.from(operatorGrid.querySelectorAll('.persona-mbti'));
    const currentIndex = buttons.findIndex((item) => item.dataset.code === entry.code);
    if (['ArrowRight', 'ArrowDown'].includes(event.key)) {
      event.preventDefault();
      buttons[(currentIndex + 1) % buttons.length].focus();
    } else if (['ArrowLeft', 'ArrowUp'].includes(event.key)) {
      event.preventDefault();
      buttons[(currentIndex - 1 + buttons.length) % buttons.length].focus();
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
      role: getSelectValue('role'),
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
        showSummary(`Saved agent persona ${saved.agent?.code ?? ''}. Reload to confirm persistence.`);
      })
      .catch((error) => {
        console.error(error);
        showSummary('Unable to persist persona state. Check the server logs for details.');
      });
  }

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
      const suggestion = {
        code: currentState.agent.code,
        rationale: currentState.agent.rationale || [],
        compatibilityScore: currentState.agent.compatibility || 0,
        roleFitScore: currentState.agent.role_fit || 0,
        blendedScore: currentState.agent.blended || 0,
        alternates: currentState.alternates || [],
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

    return {
      code: best.entry.code,
      compatibilityScore: best.compatibility.score,
      roleFitScore: best.roleFit.score,
      blendedScore: best.composite,
      rationale,
      alternates,
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
