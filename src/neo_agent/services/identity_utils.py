"""Identity utilities for deterministic agent_id generation.

Implements a stable, reproducible ID derived from NAICS code, business
function, role code, and agent name using UUID v5.
"""

from __future__ import annotations

import uuid


def generate_agent_id(
    naics_code: str, business_func: str, role_code: str, agent_name: str
) -> str:
    """Generate a deterministic agent identifier.

    Seed includes NAICS, business function, role code, and agent name. Uses
    UUIDv5 (namespace URL) and returns a short 8-char suffix for readability.
    """

    ns = uuid.NAMESPACE_URL
    naics = (naics_code or "").strip()
    func = (business_func or "").strip()
    role = (role_code or "").strip()
    name = (agent_name or "").strip()
    seed = f"{naics}|{func}|{role}|{name}".lower().replace(" ", "-")
    suffix = str(uuid.uuid5(ns, seed))[:8]
    prefix = naics if naics else "NA"
    r = role if role else "R"
    return f"AGT-{prefix}-{r}-{suffix}"
