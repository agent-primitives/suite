"""Private pin/declaration prerequisites; not finished whole-graph acceptance."""
import base64
import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from agent_suite._content import Content, Entry, retains
from agent_suite._documents import pin_literal, pin_manifest, read_documents, validate_declarations
from agent_suite._json import canonical_bytes, decode, digest_bytes
from agent_suite._models import Descriptor, Document, Source
from agent_suite._record_decode import DocumentError, read_document
from agent_suite._records import Agent, FileRef, Suite, ToolProvider
from agent_suite._schema import Bundle

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def bundle():
    return Bundle.from_bytes({p.name: p.read_bytes() for p in (ROOT / 'schema').glob('*.json')})


def content_fixture(name='minimal'):
    content = Content()
    root = ROOT / 'testdata' / name
    for p in root.rglob('*'):
        if p.is_file():
            data, path = p.read_bytes(), p.relative_to(root).as_posix()
            content.add(Entry(path, size=len(data), digest=digest_bytes(data),
                              data=data if retains(path, len(data)) else None))
    return content


def rebind_agent(content, change):
    path = 'agents/writer.json'
    value = json.loads(content.data(path))
    change(value)
    raw = canonical_bytes(value)
    content.entries[path] = replace(content.entries[path], data=raw, size=len(raw), digest=digest_bytes(raw))
    root = json.loads(content.data('agentsuite.json'))
    root['agents'][0]['descriptor'].update(digest=digest_bytes(raw), size=len(raw))
    raw = canonical_bytes(root)
    content.entries['agentsuite.json'] = replace(content.entries['agentsuite.json'], data=raw,
                                               size=len(raw), digest=digest_bytes(raw))


def test_shared_declaration_cases(bundle):
    cases = json.loads((ROOT / 'testdata/conformance/declaration-cases.json').read_bytes())['cases']
    assert len(cases) == 23 and len({c['name'] for c in cases}) == 23
    assert sum(c['valid'] for c in cases) == 4
    for case in cases:
        kind = {'agent': Agent, 'provider': ToolProvider, 'suite': Suite}[case['kind']]
        file = {'agent': 'agents/writer.json', 'provider': 'tool-providers/search/1.0.0/tool-provider.json',
                'suite': 'agentsuite.json'}[case['kind']]
        document = Document(base64.b64decode(case['bytes'], validate=True), Source(file))
        try:
            record = read_document(document, kind, bundle).record
            validate_declarations(record)
        except DocumentError as error:
            assert not case['valid'], case['name']
            pointer = error.diagnostics[0].source.pointer
            assert pointer and error.diagnostics[0].source.file == file, case['name']
            assert error.diagnostics[0].code.startswith(('schema.', 'document.', 'declaration.')), case['name']
            # Go joins errors; compare acceptance and intended field context,
            # not aggregate ordering or byte-identical diagnostic formatting.
            assert case['pointer'].startswith(pointer) or pointer.startswith(case['pointer']), case['name']
        else:
            assert case['valid'], case['name']


def test_document_error_keeps_source_for_invalid_json(bundle):
    with pytest.raises(DocumentError) as error:
        read_document(Document(b'{broken', Source('agents/broken.json')), Agent, bundle)
    assert error.value.diagnostics[0].source == Source('agents/broken.json')
    assert 'agents/broken.json' in str(error.value)


@pytest.mark.parametrize('field,value,pointer', [
    ('id', 'writer\n', '/id'),
    ('model', {'protocol': 'custom', 'model': 'custom', 'endpointEnv': 'AUTH\n'}, '/model/endpointEnv'),
])
def test_go_identifier_and_env_end_of_text_not_python_regex_dollar(bundle, field, value, pointer):
    content = content_fixture()
    data = json.loads(content.data('agents/writer.json'))
    data[field] = value
    record = read_document(Document(canonical_bytes(data), Source('agents/writer.json')), Agent, bundle).record
    with pytest.raises(DocumentError) as error:
        validate_declarations(record)
    assert error.value.diagnostics[0].source.pointer == pointer


def test_private_document_pipeline_native_directory_and_oci(tmp_path, bundle):
    from agent_suite._directory import load_directory
    from agent_suite._oci import load_oci_layout
    root = tmp_path / 'suite'
    shutil.copytree(ROOT / 'testdata/minimal', root)
    if os.name == 'nt':
        from _directory_windows_fixture import secure_fixture
        secure_fixture(root)
    directory = read_documents(load_directory(root), bundle)
    oci = read_documents(load_oci_layout(ROOT / 'testdata/conformance/oci/minimal-0644'), bundle)
    assert directory.suite.record.name == oci.suite.record.name
    assert directory.agents[0].record.id == oci.agents[0].record.id == 'writer'
    assert directory.agents[0].record.instructions.source == oci.agents[0].record.instructions.source


@pytest.mark.parametrize('target', ['policy', 'evals'])
@pytest.mark.parametrize('malformed', [False, True])
def test_optional_manifest_pins_require_canonical_object_bytes(bundle, target, malformed):
    content = content_fixture('rich-evaluations')
    agent = json.loads(content.data('agents/writer.json'))
    ref = agent['policy'] if target == 'policy' else agent['evals'][0]
    old = content.entries[ref['path']]
    data = b'{broken' if malformed else b' ' + old.data
    content.entries[ref['path']] = replace(old, data=data, size=len(data), digest=digest_bytes(data))
    def change(value):
        selected = value['policy'] if target == 'policy' else value['evals'][0]
        selected['descriptor'].update(size=len(data), digest=digest_bytes(data))
    rebind_agent(content, change)
    with pytest.raises(DocumentError) as error:
        read_documents(content, bundle)
    assert error.value.diagnostics[0].source == Source(ref['path'])
    assert error.value.diagnostics[0].code == ('document.json' if malformed else 'pin.canonical')


def test_rich_fixture_typed_declarations_keep_evaluation_and_policy_refs_raw(bundle):
    result = read_documents(content_fixture('rich-evaluations'), bundle)
    agent = result.agents[0].record
    assert agent.evals[0].path.startswith('evals/')
    assert agent.policy.path.startswith('policies/')
    assert len(result.providers) == 1
    provider = result.providers[0].record
    assert isinstance(provider, ToolProvider)
    assert provider.tools[0].input_schema.path
    assert provider.source.file.endswith('tool-provider.json')


def test_private_document_collection_and_source_pins(bundle):
    content = content_fixture()
    result = read_documents(content, bundle)
    assert isinstance(result.suite.record, Suite)
    assert result.suite.document.data == content.data('agentsuite.json')
    assert result.agents[0].record.instructions.source == Source('agents/writer.json', '/instructions')
    assert result.catalog.record.tool_providers == result.providers == ()
    assert len(result.raw_manifests) == 2  # composition/build semantics belong to3d
    assert not hasattr(result, 'verified_root_digest')
    raw = result.agents[0].document.value
    raw['id'] = 'mutated'
    assert result.agents[0].record.id == result.agents[0].document.value['id'] == 'writer'


def test_noncanonical_root_but_canonical_pinned_children(bundle):
    content = content_fixture()
    raw = json.dumps(json.loads(content.data('agentsuite.json')), indent=2).encode()
    content.entries['agentsuite.json'] = replace(content.entries['agentsuite.json'], data=raw,
                                               size=len(raw), digest=digest_bytes(raw))
    assert read_documents(content, bundle).suite.document.data == raw
    result = read_document(Document(content.data('agentsuite.json'), Source('agentsuite.json')), Suite, bundle)
    ref = result.record.agents[0]
    raw = json.dumps(json.loads(content.data(ref.path)), indent=2).encode()
    content.entries[ref.path] = replace(content.entries[ref.path], data=raw, size=len(raw), digest=digest_bytes(raw))
    ref = replace(ref, descriptor=replace(ref.descriptor, size=len(raw), digest=digest_bytes(raw)))
    with pytest.raises(DocumentError) as error:
        pin_manifest(content, ref, ref.descriptor.media_type)
    assert error.value.diagnostics[0].code == 'pin.canonical'


def test_literal_pins_never_parse_or_require_retained_body():
    content = Content()
    data = b'\xff not JSON or UTF-8'
    content.add(Entry('literal.dat', size=len(data), digest=digest_bytes(data)))
    desc = Descriptor('application/schema+json', digest_bytes(data), len(data))
    ref = FileRef('literal.dat', desc, source=Source('provider.json', '/tools/0/inputSchema'))
    assert pin_literal(content, ref, 'application/schema+json') is content.entries['literal.dat']
    for replacement, code in [(replace(desc, digest='sha256:'+'0'*64), 'pin.digest'),
                              (replace(desc, size=0), 'pin.size')]:
        with pytest.raises(DocumentError) as error:
            pin_literal(content, replace(ref, descriptor=replacement), desc.media_type)
        assert error.value.diagnostics[0].code == code
        assert error.value.diagnostics[0].source == Source('provider.json', '/tools/0/inputSchema/descriptor')
    content.entries['literal.dat'] = replace(content.entries['literal.dat'], kind='hardlink')
    with pytest.raises(DocumentError, match='regular'):
        pin_literal(content, ref, desc.media_type)


def test_manifest_pin_kind_size_hash_and_stale_ancestor(bundle):
    content = content_fixture()
    suite = read_document(Document(content.data('agentsuite.json'), Source('agentsuite.json')), Suite, bundle).record
    ref = suite.agents[0]
    for bad, code in [(replace(ref.descriptor, media_type='wrong'), 'pin.media_type'),
                      (replace(ref.descriptor, size=0), 'pin.size'),
                      (replace(ref.descriptor, digest='sha256:'+'0'*64), 'pin.digest')]:
        with pytest.raises(DocumentError) as error:
            pin_manifest(content, replace(ref, descriptor=bad), ref.descriptor.media_type)
        assert error.value.diagnostics[0].code == code
    entry = content.entries[ref.path]
    raw = entry.data.replace(b'writer', b'editor')
    content.entries[ref.path] = replace(entry, data=raw, digest=digest_bytes(raw), size=len(raw))
    with pytest.raises(DocumentError) as error:
        read_documents(content, bundle)
    assert error.value.diagnostics[0].code == 'pin.digest'


def test_identity_duplicate_and_literal_child_refusal(bundle):
    content = content_fixture()
    rebind_agent(content, lambda agent: agent.update(id='different'))
    with pytest.raises(DocumentError) as error:
        read_documents(content, bundle)
    assert error.value.diagnostics[0].code == 'document.identity'
    content = content_fixture()
    path = 'agentsuite.json'
    value = json.loads(content.data(path))
    value['agents'].append(value['agents'][0])
    raw = canonical_bytes(value)
    content.entries[path] = replace(content.entries[path], data=raw, size=len(raw), digest=digest_bytes(raw))
    with pytest.raises(DocumentError) as error:
        read_documents(content, bundle)
    assert error.value.diagnostics[0].code == 'declaration.duplicate'
    content = content_fixture()
    rebind_agent(content, lambda agent: agent['instructions']['descriptor'].update(digest='sha256:'+'0'*64))
    with pytest.raises(DocumentError) as error:
        read_documents(content, bundle)
    assert error.value.diagnostics[0].code == 'pin.digest'


def test_declaration_rules_reject_schema_permissive_unsafe_env(bundle):
    content = content_fixture()
    rebind_agent(content, lambda agent: agent['model'].update(endpointEnv='LD_PRELOAD'))
    with pytest.raises(DocumentError) as error:
        read_documents(content, bundle)
    assert error.value.diagnostics[0].code == 'declaration.env'
    assert error.value.diagnostics[0].source.pointer == '/model/endpointEnv'
