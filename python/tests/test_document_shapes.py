"""Frozen authored-document bytes, shared with actual Go package validation."""
import base64
import json
from pathlib import Path

from agent_suite._json import decode
from agent_suite._models import Source
from agent_suite._schema import Bundle

ROOT = Path(__file__).resolve().parents[2]


def test_shared_document_shape_cases():
    cases = json.loads((ROOT / 'testdata/conformance/document-shape-cases.json').read_bytes())['cases']
    assert len(cases) == 32
    names = [c['name'] for c in cases]
    assert all(names) and len(set(names)) == 32
    assert sum(c['valid'] for c in cases) == 5
    assert sum(c['regression'] for c in cases) == 25
    bundle = Bundle.from_bytes({p.name: p.read_bytes() for p in (ROOT / 'schema').glob('*.json')})
    for case in cases:
        assert type(case['valid']) is bool and type(case['regression']) is bool
        raw = base64.b64decode(case['bytes'], validate=True)
        diagnostics = bundle.validate(case['schema'], decode(raw), Source(case['file']))
        assert (not diagnostics) == case['valid'], case['name']
        if not case['valid']:
            assert any(d.source.pointer == case['pointer'] for d in diagnostics), case['name']
