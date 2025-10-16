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
