"""Uniqueness acceptance/diagnostics and deterministic work, never timing budgets."""
import itertools
import json
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction

import pytest
from jsonschema import Draft202012Validator
from jsonschema import _utils

from agent_suite._graph import read_graph
from agent_suite._json import Number, canonical_bytes, digest_bytes
from agent_suite._models import Diagnostic, Source
from agent_suite._schema import Bundle
from test_documents import ROOT, content_fixture, store_root

DRAFT = 'https://json-schema.org/draft/2020-12/schema'


def document(identity, **keywords):
    return {'$schema':DRAFT, '$id':'https://example.test/'+identity, **keywords}


def make_bundle(*schemas):
    return Bundle.from_bytes({str(i)+'.json':json.dumps(s).encode() for i,s in enumerate(schemas)})


def stock(bundle, name, value, source):
    return [Diagnostic(Source(source.file, source.pointer+''.join(
        '/'+str(p).replace('~','~0').replace('/','~1') for p in e.absolute_path)),
        'schema.'+str(e.validator), 'schema constraint '+str(e.validator)+' failed')
        for e in Draft202012Validator(bundle.schemas[name], registry=bundle.registry).iter_errors(value)]


def test_json_uniqueness_matches_stock_equality_and_diagnostics():
    bundle = make_bundle(document('unique', uniqueItems=True))
    source = Source('input.json', '/base')
    values = [None, False, True, 0, -0.0, 1, 1.0, Number('1'), Number('1.0'), Number('1e0'),
              Number('-0'), Number('0'), 2**53, 2**53+1, float(2**53), '1', [], [1, True], [True, 1],
              {}, {'x':True}, {'x':1}, {'a':1,'b':[False,None]}, {'b':[False,None],'a':1.0},
              {'x':{'a':[0,1]}}, {'x':{'a':[False,1]}}]
    for left, right in itertools.product(values, repeat=2):
        instance = [left, right]
        assert bundle.validate('0.json', instance, source) == stock(bundle, '0.json', instance, source)
    assert not bundle.validate('0.json', [True, 1, False, 0], source)
    assert bundle.validate('0.json', [{'a':1,'b':2}, {'b':2.0,'a':Number('1e0')}], source)
    assert not bundle.validate('0.json', [[1,2],[2,1]], source)


def test_non_json_values_keep_stock_fallback():
    class Object(dict):
        pass
    bundle = make_bundle(document('fallback', uniqueItems=True))
    nan = float('nan')
    for instance in [[Decimal('1'), 1], [Fraction(1,2), 0.5], [(1,), [1]],
                     [Object(x=1), {'x':1.0}], [nan,nan], [float('nan'),float('nan')],
                     [1,nan,1], [float('inf'),float('inf')], [b'a',b'a']]:
        assert bundle.validate('0.json', instance, Source('f')) == stock(bundle, '0.json', instance, Source('f'))


def test_disabled_and_non_array_uniqueness_keep_stock():
    for rule in (False, True):
        bundle = make_bundle(document('guard', uniqueItems=rule))
        for instance in (None, True, 'text', {'x':1}, [1,1]):
            assert bundle.validate('0.json', instance, Source('f')) == stock(bundle, '0.json', instance, Source('f'))


@pytest.mark.parametrize('reference', ['$ref', '$dynamicRef'])
def test_unique_items_reference_diagnostics_and_work(reference, monkeypatch):
    root = document('root', type='object', properties={'a/b~c':{reference:'middle'}})
    middle = document('middle', **{reference:'leaf'})
    leaf = document('leaf', type='array', uniqueItems=True)
    bundle = make_bundle(root, middle, leaf)
    calls = count_object_comparisons(monkeypatch)
    source = Source('nested.json', '/base')
    items = [{'name':str(i), 'environment':str(i), 'secret':False} for i in range(512)]
    assert not bundle.validate('0.json', {'a/b~c':items}, source)
    assert calls[0] <= 2*len(items)
    value = {'a/b~c':items+[dict(items[0])]}
    actual = bundle.validate('0.json', value, source)
    assert actual == stock(bundle, '0.json', value, source)
    assert actual == [Diagnostic(Source('nested.json','/base/a~1b~0c'), 'schema.uniqueItems',
                                 'schema constraint uniqueItems failed')]


def count_object_comparisons(monkeypatch):
    count = [0]
    original = _utils.equal
    def equal(left, right):
        if isinstance(left, dict) and isinstance(right, dict) and 'environment' in left and 'environment' in right:
            count[0] += 1
        return original(left, right)
    monkeypatch.setattr(_utils, 'equal', equal)
    return count


def test_comparison_counter_observes_stock_all_pairs(monkeypatch):
    items = [{'name':str(i), 'environment':str(i), 'secret':False} for i in range(64)]
    calls = count_object_comparisons(monkeypatch)
    assert not list(Draft202012Validator({'uniqueItems':True}).iter_errors(items))
    assert calls[0] == len(items)*(len(items)-1)//2


@pytest.mark.parametrize('size', [256,512,1024,2048])
def test_wide_valid_execution_uniqueness_work(size, monkeypatch):
    bundle = Bundle.from_bytes({p.name:p.read_bytes() for p in (ROOT/'schema').glob('*.json')})
    content = content_fixture()
    path = 'build-profiles/default.json'
    value = json.loads(content.data(path))
    value['execution'] = dict(kind='http-v1', protocol='openai-chat-v1', port=8080, healthPath='/healthz',
        inputs=[{'name':'input'+str(i), 'environment':'INPUT_'+str(i), 'secret':False} for i in range(size)])
    raw = canonical_bytes(value)
    content.entries[path] = replace(content.entries[path], data=raw, size=len(raw), digest=digest_bytes(raw))
    root = json.loads(content.data('agentsuite.json'))
    root['buildProfiles'][0]['descriptor'].update(size=len(raw), digest=digest_bytes(raw))
    store_root(content, root)
    calls = count_object_comparisons(monkeypatch)
    import agent_suite._schema_uniqueness as uniqueness
    steps = [0]
    original_key = uniqueness._key
    def key(value):
        steps[0] += 1
        return original_key(value)
    monkeypatch.setattr(uniqueness, '_key', key)
    assert len(read_graph(content,bundle).build_profiles[0].record.execution.inputs) == size
    assert calls[0] <= 2*size
    assert 4*size <= steps[0] <= 8*size+64
    # Real whole-object duplicates still diagnose at the owning array, regardless of position.
    for position in (0, size//2, size):
        duplicated = list(value['execution']['inputs'])
        duplicated.insert(position, dict(duplicated[-1]))
        value['execution']['inputs'] = duplicated
        calls[0] = steps[0] = 0
        diagnostics = bundle.validate('build-profile.schema.json', value, Source(path))
        assert diagnostics == [Diagnostic(Source(path,'/execution/inputs'), 'schema.uniqueItems',
                                           'schema constraint uniqueItems failed')]
        assert calls[0] <= 2*len(duplicated)
        assert 4*len(duplicated) <= steps[0] <= 8*len(duplicated)
        value['execution']['inputs'].pop(position)


def test_wide_resolved_provider_objects_keep_schema_uniqueness(monkeypatch):
    bundle = Bundle.from_bytes({p.name:p.read_bytes() for p in (ROOT/'schema').glob('*.json')})
    value = json.loads((ROOT/'testdata/minimal/compositions/writer-linux-amd64.json').read_bytes())
    value['toolProviders'] = [dict(id='provider'+str(i), version='1.0.0', manifestDigest='sha256:'+'a'*64,
        variantDigest='sha256:'+'b'*64, executionMode='shared-sandbox') for i in range(1024)]
    calls = [0]
    original = _utils.equal
    def equal(left,right):
        if isinstance(left,dict) and isinstance(right,dict) and 'manifestDigest' in left and 'manifestDigest' in right:
            calls[0] += 1
        return original(left,right)
    monkeypatch.setattr(_utils,'equal',equal)
    assert not bundle.validate('composition.schema.json',value,Source('composition.json'))
    assert calls[0] <= 2048
    value['toolProviders'].append(dict(value['toolProviders'][0]))
    actual = bundle.validate('composition.schema.json',value,Source('composition.json'))
    assert actual == stock(bundle,'composition.schema.json',value,Source('composition.json'))


def test_schema_views_preserve_original_resources_and_self_references(monkeypatch):
    schema = document('self', **{'$defs':{'array':{'uniqueItems':True}},
        'type':'object','properties':{'values':{'$ref':'#/$defs/array'}, 'child':{'$ref':'#'}},
        'const':{'literal':{'$schema':'untouched'}}})
    # Literal schema-looking data must never be transformed; keep a separate self-ref shape.
    bundle = make_bundle(schema)
    assert bundle.schemas['0.json'] == schema
    assert bundle.registry.resolver('https://example.test/self').lookup('#').contents == schema
    del schema['const']
    bundle = make_bundle(schema)
    calls = count_object_comparisons(monkeypatch)
    items = [{'environment':str(i)} for i in range(256)]
    value = {'values':items,'child':{'values':items}}
    assert not bundle.validate('0.json',value,Source('f'))
    assert calls[0] <= 4*len(items)
    value['child']['values'] = [{'x':True},{'x':1}]
    assert bundle.validate('0.json',value,Source('f')) == stock(bundle,'0.json',value,Source('f'))


def test_dynamic_anchor_rebinding_keeps_stock_diagnostics():
    base = document('tree', **{'$dynamicAnchor':'node','type':'object', 'properties':{
        'values':{'type':'array','uniqueItems':True},'child':{'$dynamicRef':'#node'}}})
    strict = document('strict', **{'$dynamicAnchor':'node','$ref':'tree','required':['values']})
    bundle = make_bundle(base,strict)
    for value in ({'values':[],'child':{}}, {'values':[],'child':{'values':[{'x':1},{'x':1.0}]}}):
        assert bundle.validate('1.json',value,Source('f')) == stock(bundle,'1.json',value,Source('f'))


def test_mixed_and_nested_dialects_keep_stock_semantics():
    foreign = document('foreign', **{'$ref':'target'})
    foreign['$schema'] = 'http://json-schema.org/draft-07/schema#'
    target = document('target', prefixItems=[{'type':'integer'}], items=False)
    root = document('mixed', **{'$ref':'foreign'})
    bundle = make_bundle(root,foreign,target)
    for value in ([1], ['wrong'], [1,2]):
        assert bundle.validate('0.json',value,Source('f')) == stock(bundle,'0.json',value,Source('f'))
    root = document('nested', **{'$defs':{'foreign':foreign},'$ref':'#/$defs/foreign'})
    bundle = make_bundle(root,target)
    assert bundle.validate('0.json',[1],Source('f')) == stock(bundle,'0.json',[1],Source('f'))


def test_pointer_to_foreign_dialect_in_unknown_keyword_keeps_stock():
    foreign = document('hidden', **{'$ref':'target'})
    foreign['$schema'] = 'http://json-schema.org/draft-07/schema#'
    root = document('root', hidden=foreign, **{'$ref':'#/hidden'})
    target = document('target', prefixItems=[{'type':'integer'}], items=False)
    bundle = make_bundle(root,target)
    for value in ([1], ['wrong'], [1,2]):
        assert bundle.validate('0.json',value,Source('f')) == stock(bundle,'0.json',value,Source('f'))


def test_reference_to_schema_metadata_preserves_previous_behavior():
    schema = document('metadata', **{'$ref':'#/$schema'})
    bundle = make_bundle(schema)
    def outcome(validate):
        try:
            return validate()
        except Exception as error:
            return type(error), str(error)
    assert outcome(lambda:bundle.validate('0.json',None,Source('f'))) == outcome(lambda:stock(bundle,'0.json',None,Source('f')))
