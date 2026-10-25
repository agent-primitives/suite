"""Both implementations consume the same literal string-boundary values."""
import json
from pathlib import Path

from agent_suite._models import Source
from agent_suite._schema import Bundle

ROOT = Path(__file__).resolve().parents[2]


def test_shared_string_length_cases():
    bundle = Bundle.from_bytes({p.name: p.read_bytes() for p in (ROOT / 'schema').glob('*.json')})
    cases = json.loads((ROOT / 'testdata/conformance/string-length-cases.json').read_bytes())['cases']
    assert len(cases) == 21
    names = [c['name'] for c in cases]
    assert all(names) and len(set(names)) == len(names)
    assert sum(c['target'] == 'agentDescription' for c in cases) == 9
    assert sum(c['target'] == 'remoteHeaderName' for c in cases) == 4
    assert sum(c['target'] == 'runtimeABIVersion' for c in cases) == 3
    assert sum(c['target'] == 'inventoryComponent' for c in cases) == 3
    assert sum(c['target'] == 'inventoryLinkTarget' for c in cases) == 2
    for case in cases:
        assert type(case['valid']) is bool
        if case['target'] == 'agentDescription':
            document = json.loads((ROOT / 'testdata/minimal/agents/writer.json').read_bytes())
            document['description'] = case['value']
            schema, pointer = 'agent.schema.json', '/description'
        elif case['target'] == 'remoteHeaderName':
            document = json.loads((ROOT / 'testdata/remote-mcp/tool-provider.json').read_bytes())
            document['remote']['headers'][0]['name'] = case['value']
            schema, pointer = 'tool-provider.schema.json', '/remote/headers/0/name'
        elif case['target'] in ('runtimeABIVersion', 'inventoryComponent', 'inventoryLinkTarget'):
            document = json.loads((ROOT / 'testdata/tool-providers/opa-tool-provider.json').read_bytes())
            variant = document['variants'][0]
            if case['target'] == 'runtimeABIVersion':
                owner, field = variant['runtime'], 'abiVersion'
                pointer = '/variants/0/runtime/abiVersion'
            else:
                field = 'linkTarget' if case['target'] == 'inventoryLinkTarget' else 'component'
                owner = variant['files'][0]
                pointer = '/variants/0/files/0/' + field
            if case.get('omit'):
                owner.pop(field, None)
            else:
                owner[field] = case['value']
            schema = 'tool-provider.schema.json'
        else:
            raise AssertionError('unknown string-length target')
        diagnostics = bundle.validate(schema, document, Source('fixture.json'))
        assert (not diagnostics) == case['valid'], case['name']
        if not case['valid']:
            assert any(d.source.pointer == pointer for d in diagnostics), case['name']
