"""Exact Suite root bytes shared with Go's semantic loader and full validator."""
import base64
import json
from pathlib import Path

from agent_suite._json import decode
from agent_suite._models import Source
from agent_suite._schema import Bundle

ROOT = Path(__file__).resolve().parents[2]


def test_shared_catalog_reference_cases():
    cases = json.loads((ROOT / 'testdata/conformance/catalog-reference-cases.json').read_bytes())['cases']
    assert len(cases) == 5
    names = [c['name'] for c in cases]
    assert all(names) and len(set(names)) == 5
    assert sum(c['valid'] for c in cases) == 2
    bundle = Bundle.from_bytes({p.name: p.read_bytes() for p in (ROOT / 'schema').glob('*.json')})
    for case in cases:
        assert type(case['valid']) is bool
        assert case['file'] == 'agentsuite.json' and case['schema'] == 'suite.schema.json'
        raw = base64.b64decode(case['bytes'], validate=True)
        diagnostics = bundle.validate(case['schema'], decode(raw), Source(case['file']))
        assert (not diagnostics) == case['valid'], case['name']
        if not case['valid']:
            assert any(d.source == Source(case['file'], case['pointer']) and d.code == case['code']
                       for d in diagnostics), (case['name'], diagnostics)
