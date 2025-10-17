ADR 0003: Intake Flow Reorder and Gated Actions

Status: Accepted
Date: 2025-10-17

Context
- Persona alignment appears before role selection, reducing context quality.
- NAICS fields are mixed into Agent Profile; gating for repo generation is permissive.

Decision
- Reorder the intake sections to: Agent Profile → Business Context (NAICS + Domain) → Business Function & Role → Persona Alignment → Toolsets → Attributes → Preferences → LinkedIn → Custom Notes.
- Gate Generate Agent Repo on agent_name, naics_code, business_function, and role (role_code or role_title).
- Disable Persona Suggest until a role is selected; enable on role:changed.
- Maintain all existing hidden-field contracts and APIs. Small diffs only.

Consequences
- Clearer UX; reduces invalid submissions; persona suggestions gain correct context.
- Minimal risk to existing selectors since data-* hooks are kept.

Alternatives Considered
- Keep current order and rely on validation: rejected; poorer UX and weaker persona context.
- Add server-side gating only: rejected; users still face confusing UI and broken flow.

Rollback Plan
- Revert FORM_TEMPLATE section order and JS gating changes. No data migration required.

