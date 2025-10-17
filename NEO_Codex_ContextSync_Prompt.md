Role: You are Codex acting as Senior Full-Stack + Repo Analyst, collaborating with NEO_CAIO’s CPA.

Mission: Build a concise “What we’ve built so far” brief so we can run an Executive GroupThink on the Project Agent NEO Toolsets feature (incl. MCP/connectors strategy). Use only the repository facts summarized below; do not invent missing pieces. Return the output sections exactly as specified.

Repository anchors (high-signal):
- Directory scaffold + packs (20-file GEN2 repo). :contentReference[oaicite:0]{index=0}
- Global runtime contract (time prefs, constraints, routing, KPIs). :contentReference[oaicite:1]{index=1}
- Operating rules (RBAC, human-in-the-loop, gates). :contentReference[oaicite:2]{index=2}
- Tool+Data Registry (tools, connectors, scopes, secrets policy). :contentReference[oaicite:3]{index=3}
- Prompt Pack (reasoning patterns, output contracts). :contentReference[oaicite:4]{index=4} :contentReference[oaicite:5]{index=5}
- Workflow Pack (micro-loops, gates, rollback). :contentReference[oaicite:6]{index=6}
- KPI & Eval targets (PRI/HAL/AUD). :contentReference[oaicite:7]{index=7}
- Memory Schema (scopes, retention, redaction). :contentReference[oaicite:8]{index=8}
- Safety & Privacy guardrails. :contentReference[oaicite:9]{index=9}
- Observability & telemetry spec. :contentReference[oaicite:10]{index=10}
- Manifests + Role recipes (AIA-P / CAIO). :contentReference[oaicite:11]{index=11} :contentReference[oaicite:12]{index=12}

Focus question: Given our existing Tool+Data Registry and guardrails, what’s the best near-term path to expose external app capabilities to NEO agents (e.g., Gmail/Outlook/HubSpot/LinkedIn) using (a) OpenAI Connectors, (b) an MCP universal server (e.g., Rube), (c) curated first-party MCP servers, or (d) a hybrid—while meeting gates and governance?

Deliverables (return exactly these sections):
1) Snapshot (≤150 words): What we’ve built, with 3 bullets on Toolsets maturity. Cite packs inline by filename.
2) Options Matrix (table): {Option, What it enables, Security/Gov notes, Build effort, UX, Time-to-Value, Risks}.
   Options: OpenAI Connectors; Universal MCP (Rube-style); Curated First-Party MCPs; Hybrid.
3) Guardrails & Gates Fit (bullets): Map each option to RBAC, approval flows, KPI gates, observability hooks. :contentReference[oaicite:13]{index=13} :contentReference[oaicite:14]{index=14} :contentReference[oaicite:15]{index=15}
4) Minimal Viable Slice (checklist): the smallest end-to-end demo using our “connectors” entries and least-privilege scopes. :contentReference[oaicite:16]{index=16}
5) Open Questions (≤8) + Next Experiments (≤3), each with a measurable success criterion.

Constraints:
- Honor least-privilege & change-control for new scopes; require CAIO approval for expansions. :contentReference[oaicite:17]{index=17}
- Keep outputs decision-ready, no code unless essential, and reference the exact pack names when relevant.

Return format: Markdown with the 5 sections only.
