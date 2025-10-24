# Intake Flow Repo Generation Fix - Implementation Summary

## Overview
Fixed the intake flow to deterministically generate complete 20-file repos in `generated_repos` while preserving Agent ID and Business Function/Role selections across re-renders. Also ensured the "Generate Agent Repo" button works with proper fallback.

## Changes Implemented

### 1. Server-Side Changes (`src/neo_agent/intake_app.py`)

#### POST "/" Handler - Build Repo on Profile Submit
- **Line ~1703-1743**: Modified the form submission handler to:
  - Create a unique subdirectory under `generated_repos` based on agent name and version
  - Call `write_repo_files()` to generate all 20 pack files
  - Generate and write `INTEGRITY_REPORT.json` 
  - Update success notice to include repo directory name
  - Handle failures gracefully without breaking the profile generation flow

#### /api/agent/generate Endpoint - API Repo Generation
- **Line ~1541-1613**: Enhanced the API endpoint to:
  - Accept JSON payload with profile data
  - Normalize v3 context/role using `normalize_context_role()`
  - Handle empty or missing region values (defaults to `["CA"]`)
  - Create unique repo subdirectory with slug-based naming
  - Write all repo files including integrity report
  - Return JSON with status, output directory, and integrity checks

#### Identity and State Persistence
- **Line ~1393-1425**: Modified `_build_profile()` to:
  - Persist `identity.agent_id` from form input
  - Preserve `business_function`, `role_code`, `role_title`, and `role_seniority`
  - Store all identity fields (display_name, owners, no_impersonation)

#### Form Rendering - State Bootstrap
- **Line ~915-925**: Enhanced `render_form()` to:
  - Extract `agent_id` from profile and inject into form's hidden input
  - Set `window.__FUNCTION_ROLE_STATE__` with business function and role selections
  - Include routing defaults JSON for role-based configuration

### 2. Normalization Adapter (`src/neo_agent/adapters/normalize_v3.py`)

#### normalize_context_role() Enhancement
- **Line ~67-70**: Updated to handle empty region arrays:
  - Check if region is not a list OR is empty
  - Default to `["CA"]` when region is missing or empty
  - Ensures regulatory frameworks are always computed

### 3. Frontend Changes

#### Generate Agent Button (`src/ui/generate_agent.js`)
- **Line ~188-217**: Enhanced with robust fallback:
  - Try API endpoint `/api/agent/generate` first
  - On 404 error, fall back to form submission with hidden marker
  - On fetch failure, also attempt form fallback
  - Improved user feedback messages

#### Function/Role Picker (`src/ui/function_role.js`)
- **Line ~24-39**: Bootstrap state from `window.__FUNCTION_ROLE_STATE__`:
  - Set hidden field values on page load
  - Preserve business function, role code, title, and seniority
  - Maintain routing defaults JSON

- **Line ~333-353**: Enhanced `initialLoad()`:
  - Populate function select from bootstrap state
  - Restore role selection from hidden field
  - Keep select enabled when prepopulated
  - Handle cases where role not yet in list but code exists

### 4. Test Coverage (`tests/test_intake_repo_generation.py`)

Created comprehensive integration tests:

1. **test_post_generates_full_repo**: Verifies POST "/" creates repo with 20+ files
2. **test_api_agent_generate_endpoint**: Validates API endpoint creates repo correctly
3. **test_agent_id_persists_across_rerender**: Confirms agent_id survives form submission
4. **test_function_role_state_persists**: Ensures function/role selections remain after submit
5. **test_normalization_with_empty_region**: Tests normalizer defaults empty region to CA
6. **test_normalization_with_region**: Verifies normalizer uses provided region

All tests pass ✓

## Technical Details

### Repo Directory Structure
Each generated repo is created with a unique slug:
```
generated_repos/
  └── {agent-name}-{version}/
      ├── README.md
      ├── neo_agent_config.json
      ├── 01_README+Directory-Map_v2.json
      ├── 02_Role-Profile_Spec_v2.json
      ├── ...
      ├── 20_Overlay-Pack_Enterprise_v1.json
      └── INTEGRITY_REPORT.json
```

### State Preservation Flow
1. Form submission → `_build_profile()` captures identity + function/role
2. Profile saved to disk with all selections
3. `render_form()` reads profile and injects values into HTML
4. JavaScript `__FUNCTION_ROLE_STATE__` bootstraps pickers
5. Hidden inputs maintain values for subsequent submissions

### Normalization Pipeline
```
Form Data → v3 Payload → normalize_context_role() → Merged Profile → write_repo_files()
                ↓
        role_profile + sector_profile
```

## Acceptance Criteria Met

✅ Fill intake → Generate Agent Profile → New folder in `generated_repos` with 20+ files  
✅ Agent ID and Function/Role remain populated after submit  
✅ Generate Agent Repo button works (calls API or falls back to POST "/")  
✅ All pytest tests pass (37/37)  
✅ Browser caching tolerance via robust state management  
✅ Empty region defaults to CA with proper regulatory mapping  

## Files Modified

1. `src/neo_agent/intake_app.py` - Main server logic
2. `src/neo_agent/adapters/normalize_v3.py` - V3 normalization
3. `src/ui/generate_agent.js` - Button handler with fallback
4. `src/ui/function_role.js` - State persistence
5. `tests/test_intake_repo_generation.py` - New integration tests

## Non-Breaking Changes

- All existing tests continue to pass
- No changes to UI layout or major refactoring
- Existing button preserved with enhanced functionality
- Backward compatible with old profiles

## How to Test Locally

```bash
# Install dependencies
pip install -e .[dev]

# Run tests
python -m pytest -q

# Start server
python -m neo_agent.intake_app

# Visit http://127.0.0.1:5000
# Fill form → Generate Agent Profile → Check generated_repos/
```
