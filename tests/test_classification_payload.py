from __future__ import annotations

import json
from pathlib import Path
from neo_agent.intake_app import create_app


def test_classification_hidden_fields_persist(tmp_path: Path) -> None:
    app = create_app(base_dir=tmp_path)
    # Simulate form submission payload mapping (WSGI parse_qs style: values are lists)
    payload = {
        'agent_name': ['Classifier Agent'],
        'agent_version': ['1.0.0'],
        'agent_persona': ['INTJ'],
        'domain': ['Finance'],
        'role': ['Enterprise Analyst'],
        'naics_code': ['311111'],
        'naics_title': ['Sample Industry'],
        'naics_level': ['6'],
        'naics_lineage_json': [json.dumps([
            {'code': '31', 'title': 'Manufacturing', 'level': 2},
            {'code': '311', 'title': 'Food Manufacturing', 'level': 3},
            {'code': '3111', 'title': 'Animal Food Manufacturing', 'level': 4},
            {'code': '31111', 'title': 'Animal (except Poultry) Food Mfg', 'level': 5},
            {'code': '311111', 'title': 'Dog and Cat Food Manufacturing', 'level': 6},
        ])],
        'function_category': ['Strategic'],
        'function_specialties_json': [json.dumps(['Planning','Governance'])],
    }
    profile = app._build_profile(payload, {})
    classification = profile.get('classification', {})
    naics = classification.get('naics')
    assert naics is not None, 'NAICS block missing in classification'
    assert naics.get('code') == '311111'
    assert naics.get('level') == 6
    assert isinstance(naics.get('lineage'), list)
    function = classification.get('function')
    assert function is not None, 'Function block missing'
    assert function.get('category') == 'Strategic'
    assert function.get('specialties') == ['Planning','Governance']
