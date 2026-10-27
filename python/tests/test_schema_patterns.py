import json
from pathlib import Path

import pytest

from agent_suite._models import Document,Source
from agent_suite._record_decode import read_document
from agent_suite._records import EvaluationCase
from agent_suite._schema import Bundle

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def bundle():
    return Bundle.from_bytes({p.name:p.read_bytes() for p in (ROOT/'schema').glob('*.json')})


@pytest.mark.parametrize('value', ['\x1c','\x1d','\x1e','\x1f','\x0b','\x85','\xa0','\ufeff'])
def test_owned_nonspace_uses_go_schema_character_class(bundle,value):
    original = json.loads((ROOT/'testdata/coordinator-workers/evals/writer/cases/capital.json').read_bytes())
    original['input'] = value
    document = Document(json.dumps(original,ensure_ascii=False).encode(),Source('evals/writer/cases/capital.json'))
    # Go regexp's Perl whitespace class is TAB/LF/FF/CR/space, not Unicode
    # TrimSpace, Python's Unicode whitespace, or Python re.ASCII (which adds VT).
    assert not bundle.validate('eval-case.schema.json',document.value,document.source)
    assert read_document(document,EvaluationCase,bundle).record.input == value


def test_unknown_noncritical_value_has_same_schema_flavor(bundle):
    value = json.loads((ROOT/'testdata/coordinator-workers/evals/writer/cases/capital.json').read_bytes())
    value['assertions'] = [dict(id='future',type='future',critical=False,value='\x1c')]
    document = Document(json.dumps(value).encode(),Source('evals/writer/cases/capital.json'))
    case = read_document(document,EvaluationCase,bundle).record
    assert case.assertions[0].value == '\x1c'


@pytest.mark.parametrize('value', ['',' ','\t','\n','\f','\r'])
def test_owned_nonspace_still_refuses_go_schema_blanks(bundle,value):
    document = json.loads((ROOT/'testdata/coordinator-workers/evals/writer/cases/capital.json').read_bytes())
    document['input'] = value
    diagnostics = bundle.validate('eval-case.schema.json',document,Source('case.json'))
    assert [(d.code,d.source.pointer) for d in diagnostics] == [('schema.pattern','/input')]


def test_foreign_and_mixed_bundles_keep_stock_pattern_semantics():
    schema = {'$schema':'https://json-schema.org/draft/2020-12/schema',
              '$id':'https://example.test/schema','type':'string','pattern':r'\S'}
    owned = dict(schema, **{'$id':'https://suite.agent-primitives.dev/schema/draft/probe.schema.json'})
    for schemas in ({'foreign.json':schema},{'foreign.json':schema,'owned.json':owned}):
        bundle = Bundle.from_bytes({k:json.dumps(v).encode() for k,v in schemas.items()})
        for name in schemas:
            assert [d.code for d in bundle.validate(name,'\x1c',Source('input'))] == ['schema.pattern']


def test_schema_pattern_assets_and_registry_remain_original(bundle):
    schema = bundle.schemas['eval-case.schema.json']
    assert schema['properties']['input']['pattern'] == r'\S'
    assert bundle.registry.contents(schema['$id']) == schema
