(function(){
  // Lightweight dynamic loader for functions catalog
  var FUNCTIONS_CATALOG = null;
  function loadFunctionsCatalog(){
    if(FUNCTIONS_CATALOG) return Promise.resolve(FUNCTIONS_CATALOG);
    return fetch('/data/functions/functions_catalog.json').then(function(r){return r.ok?r.json():{};}).catch(function(){return {};}).then(function(d){FUNCTIONS_CATALOG=d; return d;});
  }
  function dispatch(name, detail){
    try { window.dispatchEvent(new CustomEvent(name,{detail:detail})); } catch(_){}
  }
  function $(rootOrSelector, sel){
    if (typeof rootOrSelector === 'string') { return document.querySelector(rootOrSelector); }
    return rootOrSelector.querySelector(sel);
  }
  function asciiStatus(text){ return String(text||'').normalize ? String(text||'').normalize('NFKD') : String(text||''); }
  function debounce(fn, wait){ var t; var lastCtrl=null; return function(arg){ if(lastCtrl&&lastCtrl.abort){ lastCtrl.abort(); } if(t){ clearTimeout(t);} var ctrl = new AbortController(); lastCtrl=ctrl; t=setTimeout(function(){ fn(arg, ctrl); }, wait||300); return ctrl; }; }
  function createOption(node){ var o=document.createElement('option'); o.value=node.code; o.textContent=node.code+' - '+node.title; return o; }

  // Hidden fields
  var hiddenNaicsCode = document.querySelector('input[name="naics_code"]');
  var hiddenNaicsTitle = document.querySelector('input[name="naics_title"]');
  var hiddenNaicsLevel = document.querySelector('input[name="naics_level"]');
  var hiddenNaicsLineage = document.querySelector('input[name="naics_lineage_json"]');
  var hiddenFuncCategory = document.querySelector('input[name="function_category"]');
  var hiddenFuncSpecialties = document.querySelector('input[name="function_specialties_json"]');

  // NAICS Selector Wiring (2/3/4/5/6 dropdown cascade)
  var naicsRoot = document.querySelector('[data-naics-selector]');
  if(naicsRoot){
    var searchBox = $('[data-naics-selector] [data-naics-search]');
    var resultsDiv = $('[data-naics-selector] [data-naics-results]');
    var sel2 = $('[data-naics-selector] [data-naics-level2]');
    var sel3 = $('[data-naics-selector] [data-naics-level3]');
    var sel4 = $('[data-naics-selector] [data-naics-level4]');
    var sel5 = $('[data-naics-selector] [data-naics-level5]');
    var sel6 = $('[data-naics-selector] [data-naics-level6]');
    var breadcrumb = $('[data-naics-selector] [data-naics-breadcrumb]');
    var confirmBtn = $('[data-naics-selector] [data-naics-confirm]');
    var lineageState = [];

    function renderLineage(line){
      if(!line || !Array.isArray(line) || line.length===0){
        lineageState = [];
        breadcrumb.textContent='';
        return;
      }
      lineageState = line.slice();
      breadcrumb.textContent = line.map(function(n){return n.title;}).join(' > ');
    }

    function commitHiddenNaicsSelection(){
      if(lineageState && lineageState.length){
        var leaf = lineageState[lineageState.length-1] || {};
        hiddenNaicsCode.value = leaf.code || '';
        hiddenNaicsTitle.value = leaf.title || '';
        hiddenNaicsLevel.value = leaf.level != null ? String(leaf.level) : '';
        hiddenNaicsLineage.value = JSON.stringify(lineageState.map(function(n){ return {code:n.code,title:n.title,level:n.level}; }));
      } else {
        hiddenNaicsCode.value = '';
        hiddenNaicsTitle.value = '';
        hiddenNaicsLevel.value = '';
        hiddenNaicsLineage.value = '';
        try { delete confirmBtn.dataset.naicsSelected; } catch(_){}
      }
    }

    function pick(node){
      var line = [].concat(node.parents || [], [node]);
      renderLineage(line);
      confirmBtn.disabled=false;
      confirmBtn.dataset.naicsSelected=JSON.stringify(node);
    }

    function clearResults(){ if(resultsDiv){ resultsDiv.innerHTML=''; } }

    // init dropdowns (2..6 levels)
    (function initDropdownCascade(){
      if(!sel2 || !sel3 || !sel4 || !sel5 || !sel6) return;
      // bootstrap placeholders
      sel2.innerHTML = '<option value="">Select 2-digit sector</option>';
      sel3.innerHTML = '<option value="">Select 3-digit subsector</option>';
      sel4.innerHTML = '<option value="">Select 4-digit industry group</option>';
      sel5.innerHTML = '<option value="">Select 5-digit industry</option>';
      sel6.innerHTML = '<option value="">Select 6-digit detailed industry</option>';
      sel2.disabled = sel3.disabled = sel4.disabled = sel5.disabled = sel6.disabled = true;

      // Load level 2 roots
      fetch('/api/naics/roots').then(function(r){return r.ok?r.json():null;}).then(function(d){
        if(!d||d.status!=='ok') return;
        (d.items||[]).forEach(function(item){ sel2.appendChild(createOption(item)); });
        sel2.disabled=false;
      });

      function resetBelow(sel){
        if(sel===sel2){ sel3.innerHTML='<option value="">Select 3-digit subsector</option>'; sel3.disabled=true; sel4.innerHTML='<option value="">Select 4-digit industry group</option>'; sel4.disabled=true; sel5.innerHTML='<option value="">Select 5-digit industry</option>'; sel5.disabled=true; sel6.innerHTML='<option value="">Select 6-digit detailed industry</option>'; sel6.disabled=true; }
        else if(sel===sel3){ sel4.innerHTML='<option value="">Select 4-digit industry group</option>'; sel4.disabled=true; sel5.innerHTML='<option value="">Select 5-digit industry</option>'; sel5.disabled=true; sel6.innerHTML='<option value="">Select 6-digit detailed industry</option>'; sel6.disabled=true; }
        else if(sel===sel4){ sel5.innerHTML='<option value="">Select 5-digit industry</option>'; sel5.disabled=true; sel6.innerHTML='<option value="">Select 6-digit detailed industry</option>'; sel6.disabled=true; }
        else if(sel===sel5){ sel6.innerHTML='<option value="">Select 6-digit detailed industry</option>'; sel6.disabled=true; }
      }

      sel2.addEventListener('change', function(){
        confirmBtn.disabled=true; lineageState=[]; commitHiddenNaicsSelection(); renderLineage([]);
        resetBelow(sel2);
        var val=sel2.value; if(!val) return;
        fetch('/api/naics/children/'+encodeURIComponent(val)+'?level=3').then(function(r){return r.ok?r.json():null;}).then(function(d){
          if(!d||d.status!=='ok') return; (d.items||[]).forEach(function(it){ sel3.appendChild(createOption(it)); }); sel3.disabled=false;
          // Stage breadcrumb to level 2
          fetch('/api/naics/code/'+encodeURIComponent(val)).then(function(r){return r.ok?r.json():null;}).then(function(full){ if(full&&full.status==='ok'){ renderLineage([].concat(full.entry.parents||[],[{code:full.entry.code,title:full.entry.title,level:full.entry.level}])); }});
        });
      });

      sel3.addEventListener('change', function(){
        confirmBtn.disabled=true; lineageState=[]; commitHiddenNaicsSelection(); renderLineage([]);
        resetBelow(sel3);
        var val=sel3.value; if(!val) return;
        fetch('/api/naics/children/'+encodeURIComponent(val)+'?level=4').then(function(r){return r.ok?r.json():null;}).then(function(d){
          if(!d||d.status!=='ok') return; (d.items||[]).forEach(function(it){ sel4.appendChild(createOption(it)); }); sel4.disabled=false;
          // Stage 3-digit selection in breadcrumb
          fetch('/api/naics/code/'+encodeURIComponent(val)).then(function(r){return r.ok?r.json():null;}).then(function(full){ if(full&&full.status==='ok'){ renderLineage([].concat(full.entry.parents||[],[{code:full.entry.code,title:full.entry.title,level:full.entry.level}])); }});
        });
      });

      sel4.addEventListener('change', function(){
        confirmBtn.disabled=true; lineageState=[]; commitHiddenNaicsSelection(); renderLineage([]);
        resetBelow(sel4);
        var val=sel4.value; if(!val) return;
        fetch('/api/naics/children/'+encodeURIComponent(val)+'?level=5').then(function(r){return r.ok?r.json():null;}).then(function(d){
          if(!d||d.status!=='ok') return; (d.items||[]).forEach(function(it){ sel5.appendChild(createOption(it)); }); sel5.disabled=false;
          // Stage 4-digit selection; allow confirm at 4-digit
          fetch('/api/naics/code/'+encodeURIComponent(val)).then(function(r){return r.ok?r.json():null;}).then(function(full){ if(full&&full.status==='ok'){ pick(full.entry); }});
          confirmBtn.disabled=false;
        });
      });

      sel5.addEventListener('change', function(){
        confirmBtn.disabled=true; lineageState=[]; commitHiddenNaicsSelection(); renderLineage([]);
        resetBelow(sel5);
        var val=sel5.value; if(!val) return;
        fetch('/api/naics/children/'+encodeURIComponent(val)+'?level=6').then(function(r){return r.ok?r.json():null;}).then(function(d){
          if(!d||d.status!=='ok') return; (d.items||[]).forEach(function(it){ sel6.appendChild(createOption(it)); }); sel6.disabled=false;
          // Stage 5-digit selection; allow confirm at 5-digit
          fetch('/api/naics/code/'+encodeURIComponent(val)).then(function(r){return r.ok?r.json():null;}).then(function(full){ if(full&&full.status==='ok'){ pick(full.entry); confirmBtn.disabled=false; }});
        });
      });

      sel6.addEventListener('change', function(){
        confirmBtn.disabled=true; lineageState=[]; commitHiddenNaicsSelection(); renderLineage([]);
        var val=sel6.value; if(!val) return;
        fetch('/api/naics/code/'+encodeURIComponent(val)).then(function(r){return r.ok?r.json():null;}).then(function(full){ if(full&&full.status==='ok'){ pick(full.entry); confirmBtn.disabled=false; }});
      });
    })();

    var doSearch = debounce(function(_, ctrl){
      var term = searchBox.value.trim();
      clearResults();
      if(term.length<2){ return; }
      resultsDiv.textContent = asciiStatus('Looking up...');
      fetch('/api/naics/search?q='+encodeURIComponent(term), { signal: ctrl && ctrl.signal })
        .then(function(r){return r.ok?r.json():null;})
        .then(function(data){
          resultsDiv.innerHTML='';
          if(!data||data.status!=='ok') return;
          data.items.slice(0,15).forEach(function(item){
            var btn=document.createElement('button');
            btn.type='button';
            btn.textContent=item.code+' - '+item.title;
            btn.addEventListener('click', function(){
              // Resolve full node to compute parents and set selects accordingly
              fetch('/api/naics/code/'+encodeURIComponent(item.code))
                .then(function(r){return r.ok?r.json():null;})
                .then(function(full){
                  if(!full || full.status!=='ok') return;
                  var entry = full.entry; var parents = entry.parents||[];
                  var p2 = parents.find(function(p){return p.level===2;});
                  var p3 = parents.find(function(p){return p.level===3;});
                  var p4 = parents.find(function(p){return p.level===4;});
                  var p5 = parents.find(function(p){return p.level===5;});
                  if(p2 && sel2){ sel2.value=p2.code; sel2.dispatchEvent(new Event('change')); }
                  setTimeout(function(){ if(p3 && sel3){ sel3.value=p3.code; sel3.dispatchEvent(new Event('change')); }
                    setTimeout(function(){ if(p4 && sel4){ sel4.value=p4.code; sel4.dispatchEvent(new Event('change')); }
                      setTimeout(function(){ if(p5 && sel5){ sel5.value=p5.code; sel5.dispatchEvent(new Event('change')); }
                        setTimeout(function(){ if(entry.level===6 && sel6){ sel6.value=entry.code; sel6.dispatchEvent(new Event('change')); } else if(entry.level>=4){ confirmBtn.disabled=false; }
                        }, 50);
                      }, 50);
                    }, 50);
                  }, 50);
                });
            });
            resultsDiv.appendChild(btn);
          });
        });
    }, 300);

  searchBox.addEventListener('input', function(){ doSearch(); if(!searchBox.value.trim()){ if(resultsDiv){ resultsDiv.innerHTML=''; } } });

    confirmBtn.addEventListener('click', function(){
      if(confirmBtn.disabled) return;
      try {
        // Require a staged selection
        if(!lineageState || lineageState.length===0) return;
        var node=JSON.parse(confirmBtn.dataset.naicsSelected||'null');
        if(!node) return;
        // Commit hidden fields from staged lineage, then dispatch
        commitHiddenNaicsSelection();
        dispatch('naics:selected', {code:node.code,title:node.title,level:node.level,lineage:JSON.parse(hiddenNaicsLineage.value)});
      } catch(_){ }
    });
  }

  // Function + Specialties
  var functionRoot = document.querySelector('[data-function-select]');
  if(functionRoot){
    var radios = functionRoot.querySelectorAll('input[name="function_category_choice"]');
    var specialtiesBlock = functionRoot.querySelector('[data-specialties-block]');
    var specialtyInput = functionRoot.querySelector('[data-specialty-input]');
    var chipsDiv = functionRoot.querySelector('[data-specialty-chips]');
    var currentSpecialties = [];

    function renderChips(){
      chipsDiv.innerHTML='';
      currentSpecialties.forEach(function(name){
        var btn=document.createElement('button');
        btn.type='button';
        btn.textContent=name;
        btn.setAttribute('aria-pressed','true');
        btn.addEventListener('click', function(){ toggleSpecialty(name); });
        chipsDiv.appendChild(btn);
      });
      hiddenFuncSpecialties.value=JSON.stringify(currentSpecialties);
      dispatch('specialties:changed', {specialties: currentSpecialties.slice()});
    }
    function toggleSpecialty(name){
      var idx=currentSpecialties.indexOf(name);
      if(idx>=0){ currentSpecialties.splice(idx,1);} else { currentSpecialties.push(name);} 
      renderChips();
    }

    function loadCategory(cat){
      loadFunctionsCatalog().then(function(catalog){
        var list = catalog[cat] || [];
        currentSpecialties=[]; // reset when category changes
        hiddenFuncCategory.value=cat;
        specialtiesBlock.hidden=false;
        // Render category specialties as unselected chips (press to add)
        chipsDiv.innerHTML='';
        list.forEach(function(item){
          var btn=document.createElement('button');
          btn.type='button';
            btn.textContent=item;
            btn.setAttribute('aria-pressed','false');
            btn.addEventListener('click', function(){
              if(currentSpecialties.indexOf(item)===-1){ currentSpecialties.push(item); }
              renderChips();
            });
            chipsDiv.appendChild(btn);
        });
        dispatch('function:selected', {category:cat});
      });
    }

    specialtyInput.addEventListener('keydown', function(e){
      if(e.key==='Enter'){
        e.preventDefault();
        var val=specialtyInput.value.trim();
        if(val && currentSpecialties.indexOf(val)===-1){ currentSpecialties.push(val); renderChips(); }
        specialtyInput.value='';
      }
    });

    radios.forEach(function(r){
      r.addEventListener('change', function(){ if(r.checked){ loadCategory(r.value); } });
    });
  }
})();
