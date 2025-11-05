(function () {
  const root = document.querySelector('[data-domain-selector]');
  if (!root) {
    return;
  }

  const banner = root.querySelector('[data-domain-banner]');
  const button = root.querySelector('[data-domain-banner-button]');
  const label = root.querySelector('[data-domain-name]');
  const input = root.querySelector('[data-domain-input]');
  const form = root.closest('form');
  const domainMap = window.__DOMAIN_AUTODERIVE__ || {};

  function normaliseFunctionKey(value) {
    return String(value || '')
      .replace(/&/g, ' AND ')
      .replace(/\+/g, ' AND ')
      .replace(/[^A-Z0-9]+/gi, '_')
      .replace(/_{2,}/g, '_')
      .replace(/^_|_$/g, '')
      .toUpperCase();
  }

  function inferDomain() {
    if (!form) {
      return '';
    }
    const keyField = form.querySelector('[name="business_function_key"]');
    const fnField = form.querySelector('[name="business_function"]');
    const explicit = keyField && keyField.value ? String(keyField.value) : '';
    const key = explicit || normaliseFunctionKey(fnField && fnField.value);
    return key && domainMap[key] ? String(domainMap[key]) : '';
  }

  function updateBanner() {
    if (!banner || !button || !label) {
      return;
    }
    const inferred = inferDomain();
    const override = input ? String(input.value || '').trim() : '';
    if (inferred && !override) {
      label.textContent = inferred;
      button.setAttribute('data-domain-value', inferred);
      banner.hidden = false;
    } else {
      button.removeAttribute('data-domain-value');
      banner.hidden = true;
    }
  }

  if (input) {
    input.addEventListener('input', updateBanner);
    input.addEventListener('change', updateBanner);
  }

  if (button) {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      const inferred = button.getAttribute('data-domain-value');
      if (!inferred || !input) {
        if (input) {
          input.focus();
        }
        return;
      }
      input.value = inferred;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      try {
        input.focus({ preventScroll: true });
      } catch (error) {
        input.focus();
      }
    });
  }

  function handleFunctionChange() {
    if (input && input.value && input.value.trim()) {
      return;
    }
    updateBanner();
  }

  document.addEventListener('business:functionChanged', handleFunctionChange, true);
  if (form) {
    const fnField = form.querySelector('[name="business_function"]');
    if (fnField) {
      fnField.addEventListener('change', handleFunctionChange);
      fnField.addEventListener('input', handleFunctionChange);
    }
  }

  updateBanner();
  root.dataset.domainSelectorReady = '1';
})();
