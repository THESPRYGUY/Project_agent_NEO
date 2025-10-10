from __future__ import annotations

import json
from pathlib import Path
from neo_agent.intake_app import create_app


def test_profile_schema_accepts_classification(tmp_path: Path):
    app = create_app(base_dir=tmp_path)
    payload = {
        'agent_name': ['Schema Agent'],
        'agent_version': ['1.0.0'],
        'agent_persona': ['INTP'],
        'domain': ['Finance'],
        'role': ['Enterprise Analyst'],
        'naics_code': ['311111'],
        'naics_title': ['Dog and Cat Food Manufacturing'],
        'naics_level': ['6'],
        'naics_lineage_json': [json.dumps([
            {'code': '31', 'title': 'Manufacturing', 'level': 2},
            {'code': '311', 'title': 'Food Manufacturing', 'level': 3},
            {'code': '311111', 'title': 'Dog and Cat Food Manufacturing', 'level': 6},
        ])],
        'function_category': ['Strategic'],
        'function_specialties_json': [json.dumps(['Planning'])],
    }
    profile = app._build_profile(payload, {})
    # Expect classification blocks present
    classification = profile.get('classification', {})
    assert 'naics' in classification and 'function' in classification
    # Schema validation already invoked inside _build_profile; no exception means pass.
