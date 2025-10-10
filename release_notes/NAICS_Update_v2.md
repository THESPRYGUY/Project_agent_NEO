# NAICS Update v2

Date: 2025-10-08

## What changed
- Implemented NAICS drill-down cascade (2→6) with lineage breadcrumbs
- Added debounced fuzzy search and cancellation
- Extended schema with classification block
- New endpoints: /api/naics/roots, /api/naics/children/{code}

## How to validate
1. Run server and open intake UI.
2. Search NAICS (typing fast should show ≤1 request per ~300ms).
3. Select 2-digit and drill to 6-digit. Confirm hidden fields contain `naics_code`, `naics_level`, and `naics_lineage_json` from 2→…→6.
4. Submit form and verify profile.classification.* blocks.
5. Run tests: `npm run build` then `npm test -- --runInBand`, and `pytest -q`.

## Rollback steps
- Revert to previous commit; remove new endpoints and UI cascade wiring.
- Restore `naics_reference.json` if replaced.
