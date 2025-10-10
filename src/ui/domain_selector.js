(function () {
  var CURATED_DOMAINS = null; // loaded dynamically

  var SUBDOMAIN_EXTENSIONS = {
    "Energy & Infrastructure": [
      "VPP & Grid Services",
      "Data Center Strategy",
      "Utility Interconnection",
      "Tariffs & TVE"
    ]
  };

  function normalizeTag(value) {
    var trimmed = (value || "").trim().toLowerCase();
    if (!trimmed) {
      return null;
    }
    var cleaned = trimmed
      .replace(/[^a-z0-9\s-]/g, "")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-");
    return cleaned || null;
  }

  function uniquePush(list, value) {
    return list.indexOf(value) >= 0 ? list : list.concat(value);
  }

  function createTagChip(label, onRemove) {
    var tag = document.createElement("span");
    tag.className = "ds-tag";
    tag.textContent = label;

    var removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.setAttribute("aria-label", "Remove tag " + label);
    removeButton.textContent = "x";
    removeButton.addEventListener("click", onRemove);

    tag.appendChild(removeButton);
    return tag;
  }

  function validateNaics(selection) {
    if (selection.topLevel !== "Sector Domains") {
      if (selection.naics) {
        selection = Object.assign({}, selection);
        delete selection.naics;
      }
      return selection;
    }
    return selection;
  }

  function DomainSelectorComponent(root, onChange) {
    this.root = root;
    this.onChange = onChange;
    this.topLevelSelect = root.querySelector("select[data-top-level]");
    this.subdomainSelect = root.querySelector("select[data-subdomain]");
    this.tagInput = root.querySelector("input[data-tag-input]");
    this.tagContainer = root.querySelector("[data-tags]");
    this.naicsBlock = root.querySelector('[data-naics-block]');
    this.naicsInput = root.querySelector('[data-naics-code]');
    this.naicsHint = root.querySelector('[data-naics-hint]');
    this.tags = [];
    this.currentTopLevel = "";
    this.currentSubdomain = "";
    this.currentNaics = "";
    this.naicsDebounce = null;
  this.naicsLookupToken = 0; // increments per lookup to discard stale responses
  this.hiddenField = document.querySelector('input[name="domain_selector"]');

    this.bootstrapOptions();
    this.wireEvents();
    this.root.removeAttribute("hidden");
  }

  DomainSelectorComponent.prototype.bootstrapOptions = function () {
    var _this = this;
    if (!CURATED_DOMAINS) {
      // Fetch curated list once
      fetch('/api/domains/curated')
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (data && data.status === 'ok' && data.curated) {
            CURATED_DOMAINS = data.curated;
          } else {
            // minimal fallback (subset)
            CURATED_DOMAINS = { 'Strategic Functions': ['Workflow Orchestration'] };
          }
          _this._populateTopLevels();
        })
        .catch(function () {
          CURATED_DOMAINS = { 'Strategic Functions': ['Workflow Orchestration'] };
          _this._populateTopLevels();
        });
    } else {
      _this._populateTopLevels();
    }
  };

  DomainSelectorComponent.prototype._populateTopLevels = function () {
    if (!CURATED_DOMAINS) { return; }
    var _this = this;
    Object.keys(CURATED_DOMAINS).forEach(function (topLevel) {
      var option = document.createElement('option');
      option.value = topLevel;
      option.textContent = topLevel;
      option.dataset.count = String(CURATED_DOMAINS[topLevel].length);
      _this.topLevelSelect.appendChild(option);
    });
  };

  DomainSelectorComponent.prototype.wireEvents = function () {
    var _this = this;
    this.topLevelSelect.addEventListener("change", function () {
      _this.currentTopLevel = _this.topLevelSelect.value;
      _this.populateSubdomains();
      _this.updateNaicsVisibility();
      // If top-level cleared, also clear hidden field to avoid stale JSON
      if (!_this.currentTopLevel && _this.hiddenField) { _this.hiddenField.value = ''; }
      _this.emitChange();
    });

    this.subdomainSelect.addEventListener("change", function () {
      _this.currentSubdomain = _this.subdomainSelect.value;
      _this.emitChange();
    });

    // Optional reset button (if present in template) with data-domain-reset attribute
    var resetBtn = this.root.querySelector('[data-domain-reset]');
    if (resetBtn) {
      resetBtn.addEventListener('click', function (e) {
        e.preventDefault();
        _this.clear();
        _this.emitChange();
      });
    }

    if (this.naicsInput) {
      this.naicsInput.addEventListener('input', function () {
        var value = (_this.naicsInput.value || '').replace(/[^0-9]/g, '').slice(0,6);
        if (_this.naicsInput.value !== value) {
          _this.naicsInput.value = value;
        }
        _this.currentNaics = value;
        if (_this.naicsDebounce) { clearTimeout(_this.naicsDebounce); }
        _this.naicsDebounce = setTimeout(function () { _this.lookupNaics(); }, 300);
        _this.emitChange();
      });
    }

    this.tagInput.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault();
        var normalized = normalizeTag(_this.tagInput.value);
        if (normalized) {
          _this.tags = uniquePush(_this.tags, normalized);
          _this.renderTags();
          _this.emitChange();
        }
        _this.tagInput.value = "";
      }
    });
  };

  DomainSelectorComponent.prototype.populateSubdomains = function () {
    this.subdomainSelect.innerHTML = "";
    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.disabled = true;
    placeholder.selected = true;
    placeholder.textContent = "Select a subdomain";
    this.subdomainSelect.appendChild(placeholder);

    if (!this.currentTopLevel) {
      this.subdomainSelect.disabled = true;
      this.currentSubdomain = "";
      return;
    }

  var subdomains = (CURATED_DOMAINS && CURATED_DOMAINS[this.currentTopLevel]) || [];
    var extra = SUBDOMAIN_EXTENSIONS[this.currentTopLevel] || [];
    subdomains.concat(extra).forEach(function (subdomain) {
      var option = document.createElement("option");
      option.value = subdomain;
      option.textContent = subdomain;
      placeholder.parentElement.appendChild(option);
    });

    this.subdomainSelect.disabled = false;
    this.currentSubdomain = "";
  };

  DomainSelectorComponent.prototype.renderTags = function () {
    var _this = this;
    this.tagContainer.innerHTML = "";
    this.tags.forEach(function (tag) {
      var chip = createTagChip(tag, function () {
        _this.tags = _this.tags.filter(function (item) {
          return item !== tag;
        });
        _this.renderTags();
        _this.emitChange();
      });
      _this.tagContainer.appendChild(chip);
    });
  };

  DomainSelectorComponent.prototype.emitChange = function () {
    if (!this.currentTopLevel || !this.currentSubdomain) {
      // Incomplete selection: clear hidden field to prevent stale submission
      if (this.hiddenField) { this.hiddenField.value = ''; }
      return;
    }
    var selection = { topLevel: this.currentTopLevel, subdomain: this.currentSubdomain, tags: this.tags.slice() };
    if (this.currentTopLevel === 'Sector Domains' && this.currentNaics) {
      selection.naics = { code: this.currentNaics };
    }
    selection = validateNaics(selection);
    if (this.hiddenField) {
      try { this.hiddenField.value = JSON.stringify(selection); } catch (_) { /* ignore */ }
    }
    var detail = Object.assign({}, selection);
    this.root.dispatchEvent(new CustomEvent('domain:changed', { bubbles: true, detail: detail }));
    if (typeof this.onChange === 'function') { this.onChange(detail); }
  };

  DomainSelectorComponent.prototype.clear = function () {
    this.currentTopLevel = '';
    this.currentSubdomain = '';
    this.currentNaics = '';
    this.tags = [];
    if (this.hiddenField) { this.hiddenField.value = ''; }
    this.subdomainSelect.innerHTML = '';
    this.updateNaicsVisibility();
    if (this.naicsHint) { this.naicsHint.textContent = ''; }
  };

  DomainSelectorComponent.prototype.updateNaicsVisibility = function () {
    if (!this.naicsBlock) { return; }
    var shouldShow = this.currentTopLevel === 'Sector Domains';
    this.naicsBlock.hidden = !shouldShow;
    if (!shouldShow) {
      this.currentNaics = '';
      if (this.naicsHint) { this.naicsHint.textContent = ''; }
    }
  };

  DomainSelectorComponent.prototype.lookupNaics = function () {
    var _this = this;
    if (!this.currentNaics || this.currentNaics.length < 2) {
      if (this.naicsHint) { this.naicsHint.textContent = ''; }
      return;
    }
    var code = this.currentNaics;
    var token = ++this.naicsLookupToken;
    if (this.naicsHint) { this.naicsHint.textContent = 'Looking up…'; }
    fetch('/api/naics/code/' + encodeURIComponent(code))
      .then(function (r) { return r && r.ok ? r.json() : null; })
      .then(function (data) {
        // Discard if a newer lookup started
        if (token !== _this.naicsLookupToken) { return; }
        if (!data || data.status !== 'ok') {
          if (_this.naicsHint) { _this.naicsHint.textContent = 'No match'; }
          return;
        }
        if (_this.naicsHint) {
          _this.naicsHint.textContent = data.entry.title + ' (L' + data.entry.level + ')';
        }
      })
      .catch(function () {
        if (token !== _this.naicsLookupToken) { return; }
        if (_this.naicsHint) { _this.naicsHint.textContent = 'Lookup error'; }
      });
  };

  var DomainSelector = {
    mount: function (selector, opts) {
      var root = typeof selector === "string" ? document.querySelector(selector) : selector;
      if (!root) {
        return null;
      }
      return new DomainSelectorComponent(root, opts && opts.onChange);
    }
  };

  if (typeof window !== "undefined") {
    window.DomainSelector = DomainSelector;
  }

  if (typeof module !== "undefined" && module.exports) {
    module.exports = { DomainSelector: DomainSelector };
  }
})();
