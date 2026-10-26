"""Private composition/profile prerequisites; policies/evaluations are not complete."""
import base64
import json
import os
import shutil
from dataclasses import FrozenInstanceError, replace

import pytest

from agent_suite._content import Content, Entry
from agent_suite._graph import read_graph
from agent_suite._json import canonical_bytes, digest_bytes
from agent_suite._models import Document, Source
from agent_suite._profiles import validate_build
from agent_suite._record_decode import DocumentError, read_document
from agent_suite._records import BuildProfile, RuntimeProfile
from agent_suite._schema import Bundle
from test_documents import ROOT, content_fixture, rebind_agent, store_root


@pytest.fixture
def bundle():
    return Bundle.from_bytes({p.name:p.read_bytes() for p in (ROOT/'schema').glob('*.json')})


def build(bundle, change):
    value = json.loads((ROOT/'testdata/minimal/build-profiles/default.json').read_bytes())
    change(value)
    document = Document(canonical_bytes(value), Source('build.json'))
    assert not bundle.validate('build-profile.schema.json', document.value, document.source)
    return read_document(document, BuildProfile, bundle).record


def test_schema_valid_trailing_newline_profile_values(bundle):
    for field, code in [('id', 'build.identity'), ('image', 'build.image'),
                        ('health', 'execution.path'), ('name', 'execution.identity'),
                        ('environment', 'execution.identity')]:
        def change(value):
            if field == 'id':
                value['id'] += '\n'
            elif field == 'image':
                value['runtimeBase'][0]['imageRef'] += '\n'
                value['runtimeBase'][0]['image']['digest'] += '\n'
            else:
                item = {'name':'config', 'environment':'CONFIG', 'secret':False}
                execution = dict(kind='http-v1', protocol='openai-chat-v1', port=8080, healthPath='/healthz', inputs=[item])
                if field == 'health':
                    execution['healthPath'] += '\n'
                else:
                    item[field] += '\n'
                value['execution'] = execution
        profile = build(bundle, change)
        with pytest.raises(DocumentError) as error:
            validate_build(profile)
        assert error.value.diagnostics[0].code == code


@pytest.mark.parametrize('path', [('id',), ('configurationABI',),
    *[(implementation, field) for implementation in ('runtime', 'harness', 'renderer')
      for field in ('id', 'version', 'digest')]])
def test_runtime_tokens_do_not_inherit_schema_final_newline_anchor(bundle, path):
    from agent_suite._profiles import validate_runtime
    cases = json.loads((ROOT/'testdata/conformance/graph-cases.json').read_bytes())['cases']
    case = next(c for c in cases if c['name'] == 'runtime-two-profiles')
    entry = next(e for e in case['entries'] if e['path'] == 'runtime-profiles/orka.json')
    value = json.loads(base64.b64decode(entry['bytes']))
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] += '\n'
    document = Document(canonical_bytes(value), Source(entry['path']))
    assert not bundle.validate('runtime-profile.schema.json', document.value, document.source)
    runtime = read_document(document, RuntimeProfile, bundle).record
    with pytest.raises(DocumentError) as error:
        validate_runtime(runtime)
    assert error.value.diagnostics[0].code == 'runtime.identity'


def test_schema_valid_duplicate_execution_fields(bundle):
    for duplicate in ('name', 'environment'):
        inputs = [{'name':'config', 'environment':'CONFIG', 'secret':False},
                  {'name':'other', 'environment':'OTHER', 'secret':True}]
        inputs[1][duplicate] = inputs[0][duplicate]
        execution = dict(kind='http-v1', protocol='openai-chat-v1', port=8080, healthPath='/healthz', inputs=inputs)
        profile = build(bundle, lambda v:v.update(execution=execution))
        with pytest.raises(DocumentError) as error:
            validate_build(profile)
        assert error.value.diagnostics[0].code == 'execution.duplicate'
        assert error.value.diagnostics[0].source == Source('build.json', '/execution/inputs/1/'+duplicate)


def test_schema_valid_duplicate_image_platform(bundle):
    def change(value):
        image = json.loads(json.dumps(value['runtimeBase'][0]))
        image['image']['digest'] = 'sha256:'+'b'*64
        image['imageRef'] = 'registry.example/team/second@'+image['image']['digest']
        value['runtimeBase'].append(image)
    profile = build(bundle, change)
    with pytest.raises(DocumentError) as error:
        validate_build(profile)
    assert error.value.diagnostics[0].code == 'build.platform'
    assert error.value.diagnostics[0].source == Source('build.json', '/runtimeBase/1/platform')


def test_image_semantics_after_owning_schema(bundle):
    digest = 'sha256:'+'a'*64
    refs = [('team/image', False), ('index.docker.io/team/image', False),
            ('registry..example/team/image', False), ('registry.example:0/team/image', False),
            ('registry.example:'+('9'*5000)+'/team/image', False),
            ('registry.example:'+('0'*5000)+'1/team/image', True),
            ('registry.example:'+('0'*5000)+'/team/image', False),
            ('docker.io/'+('a'*247), True), ('docker.io/'+('a'*248), False),
            ('registry.example/'+('a'*255), True), ('registry.example/'+('a'*256), False),
            ('registry--prod.example/team/repo-a_b.c', True), ('[2001:DB8::1]/team/image', True)]
    for ref, valid in refs:
        def change(value):
            value['runtimeBase'][0]['imageRef'] = ref+'@'+digest
            value['runtimeBase'][0]['image']['digest'] = digest
        profile = build(bundle, change)
        if valid:
            validate_build(profile)
        else:
            with pytest.raises(DocumentError) as error:
                validate_build(profile)
            assert error.value.diagnostics[0].code == 'build.image'
            assert error.value.diagnostics[0].source == Source('build.json', '/runtimeBase/0/imageRef')


def test_private_graph_minimal_and_original_bytes(bundle):
    content = content_fixture()
    result = read_graph(content, bundle)
    assert len(result.build_profiles) == len(result.compositions) == 1
    assert result.runtime_profiles == result.tool_provider_compositions == ()
    assert result.build_profiles[0].document.data == content.data('build-profiles/default.json')
    with pytest.raises(FrozenInstanceError):
        result.compositions = ()
    assert not hasattr(result, 'verified_root_digest')
    assert not hasattr(result, 'package_digest')


def test_private_graph_current_pins_and_reference_identity(bundle):
    content = content_fixture()
    root = json.loads(content.data('agentsuite.json'))
    root['buildProfiles'][0]['id'] = 'different'
    store_root(content, root)
    with pytest.raises(DocumentError) as error:
        read_graph(content, bundle)
    assert error.value.diagnostics[0].code == 'graph.identity'
    assert error.value.diagnostics[0].source == Source('agentsuite.json', '/buildProfiles/0')
    content = content_fixture()
    root = json.loads(content.data('agentsuite.json'))
    root['compositions'][0]['descriptor']['digest'] = 'sha256:'+'0'*64
    store_root(content, root)
    with pytest.raises(DocumentError) as error:
        read_graph(content, bundle)
    assert error.value.diagnostics[0].code == 'pin.digest'


def test_graph_validation_does_not_evaluate_policy_semantics(bundle):
    content = content_fixture()
    # Canonical object pin is valid, but policy semantics are intentionally not.
    data = canonical_bytes({'not-a-policy':'deliberately outside this slice'})
    content.add(Entry('policies/unvalidated.json', size=len(data), digest=digest_bytes(data), data=data))
    rebind_agent(content, lambda v:v.update(policy={'path':'policies/unvalidated.json', 'descriptor':{
        'mediaType':'application/vnd.agentsuite.policy.v1+json', 'digest':digest_bytes(data), 'size':len(data)}}))
    result = read_graph(content, bundle)
    assert result.documents.suite.record.name
    assert not hasattr(result, 'validated')


def corpus_content(case):
    content = Content()
    assert case['sourceType'] in ('directory', 'archive')
    content.source_type = 'directory' if case['sourceType'] == 'directory' else ''
    for entry in case['entries']:
        data = base64.b64decode(entry['bytes'], validate=True) if entry['bytes'] is not None else None
        if data is not None:
            assert len(data) == entry['size'] and digest_bytes(data) == entry['digest']
        content.add(Entry(entry['path'], kind=entry['type'], mode=entry['mode'], uid=entry['uid'], gid=entry['gid'],
                          size=entry['size'], digest=entry['digest'], link_target=entry['linkTarget'], data=data))
    return content


@pytest.mark.parametrize('group,seed', [('buildProfiles','minimal'), ('compositions','minimal'),
    ('runtimeProfiles','runtime-two-profiles'), ('toolProviderCompositions','standalone')])
def test_schema_valid_duplicate_graph_selection_keys(bundle, group, seed):
    cases = json.loads((ROOT/'testdata/conformance/graph-cases.json').read_bytes())['cases']
    content = corpus_content(next(c for c in cases if c['name'] == seed))
    root = json.loads(content.data('agentsuite.json'))
    ref = dict(root[group][0])
    original_path = ref['path']
    ref['path'] = 'duplicates/'+original_path
    content.add(replace(content.entries[original_path], path=ref['path']))
    root[group].append(ref)
    store_root(content, root)
    document = Document(content.data('agentsuite.json'), Source('agentsuite.json'))
    assert not bundle.validate('suite.schema.json', document.value, document.source)
    with pytest.raises(DocumentError) as error:
        read_graph(content, bundle)
    assert error.value.diagnostics[0].code == 'graph.duplicate'
    assert error.value.diagnostics[0].source == Source('agentsuite.json', '/'+group+'/'+str(len(root[group])-1))


def test_stale_variant_points_to_selected_resolution(bundle):
    cases = json.loads((ROOT/'testdata/conformance/graph-cases.json').read_bytes())['cases']
    content = corpus_content(next(c for c in cases if c['name'] == 'variant-stale'))
    root = json.loads(content.data('agentsuite.json'))
    path = root['compositions'][0]['path']
    with pytest.raises(DocumentError) as error:
        read_graph(content, bundle)
    assert error.value.diagnostics[0].code == 'graph.variant'
    assert error.value.diagnostics[0].source == Source(path, '/toolProviders/0/variantDigest')


def test_shared_graph_cases(bundle):
    cases = json.loads((ROOT/'testdata/conformance/graph-cases.json').read_bytes())['cases']
    assert len(cases) == len({c['name'] for c in cases}) == 70
    assert sum(c['fullPath'] for c in cases) == 68
    assert sum(c['sourceType'] == 'archive' for c in cases) == 2
    for case in cases:
        assert type(case['valid']) is bool and type(case['fullPath']) is bool
        content = corpus_content(case)
        try:
            read_graph(content, bundle)
        except DocumentError as error:
            assert not case['valid'], (case['name'], error)
            assert error.diagnostics[0].source.file
        else:
            assert case['valid'], case['name']


def test_graph_native_directory_and_oci(tmp_path, bundle):
    from agent_suite._directory import load_directory
    from agent_suite._oci import load_oci_layout
    from test_oci import materialize
    root = tmp_path/'suite'
    shutil.copytree(ROOT/'testdata/rich-evaluations', root)
    if os.name == 'nt':
        from _directory_windows_fixture import secure_fixture
        secure_fixture(root)
    assert read_graph(load_directory(root), bundle).compositions
    layout = tmp_path/'layout'
    materialize(layout, {'layout':'minimal-0644'})
    result = read_graph(load_oci_layout(layout), bundle)
    assert result.build_profiles and result.compositions
