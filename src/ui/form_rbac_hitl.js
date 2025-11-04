(function (global) {
  const ns = global.NeoIntake || (global.NeoIntake = {});

  function createChipList(options, selectedValues, onToggle) {
    const chips = document.createElement("div");
    chips.className = "intake-chips";
    options.forEach((value) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "intake-chip";
      chip.textContent = value;
      const selected = selectedValues.includes(value);
      chip.setAttribute("data-selected", selected ? "true" : "false");
      chip.addEventListener("click", () => {
        const isSelected = chip.getAttribute("data-selected") === "true";
        chip.setAttribute("data-selected", isSelected ? "false" : "true");
        onToggle(value, !isSelected);
      });
      chips.appendChild(chip);
    });
    return chips;
  }

  ns.initRbacHitlForm = function initRbacHitlForm(container, state, defaults, emit) {
    if (!container) return;
    container.innerHTML = "";
    container.classList.add("intake-contract-card");

    state.rbac = state.rbac || {};
    state.rbac.roles = Array.isArray(state.rbac.roles) && state.rbac.roles.length
      ? state.rbac.roles.slice()
      : (defaults.roles || []).slice();

    state.human_gate = state.human_gate || {};
    state.human_gate.actions = Array.isArray(state.human_gate.actions) && state.human_gate.actions.length
      ? state.human_gate.actions.slice()
      : (defaults.human_gate_actions || []).slice();

    const title = document.createElement("h3");
    title.textContent = "RBAC & Human Gate";
    container.appendChild(title);

    const rolesHeading = document.createElement("strong");
    rolesHeading.textContent = "RBAC Roles";
    container.appendChild(rolesHeading);
    const rolesChips = createChipList(defaults.roles || [], state.rbac.roles, (value, selected) => {
      const next = new Set(state.rbac.roles || []);
      if (selected) next.add(value);
      else next.delete(value);
      state.rbac.roles = Array.from(next);
      emit();
    });
    container.appendChild(rolesChips);

    const hitlHeading = document.createElement("strong");
    hitlHeading.textContent = "Human Gate Actions";
    hitlHeading.style.marginTop = "0.75rem";
    container.appendChild(hitlHeading);
    const hitlChips = createChipList(defaults.human_gate_actions || [], state.human_gate.actions, (value, selected) => {
      const next = new Set(state.human_gate.actions || []);
      if (selected) next.add(value);
      else next.delete(value);
      state.human_gate.actions = Array.from(next);
      emit();
    });
    container.appendChild(hitlChips);
  };
})(typeof window !== "undefined" ? window : globalThis);
