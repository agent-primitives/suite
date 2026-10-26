"""Bundled-subsystem prerequisites, not complete package graph acceptance."""
import base64
import json
import os
import shutil
from collections import Counter
from dataclasses import replace

import pytest

from agent_suite._bundles import add_variant_destinations, bundle_closure, validate_bundles
from agent_suite._content import Content, Entry
from agent_suite._documents import read_documents
from agent_suite._json import digest_bytes, variant_bytes
from agent_suite._models import Document, Source
from agent_suite._record_decode import DocumentError, read_document
from agent_suite._records import ToolProvider, ToolProviderDependency
from agent_suite._schema import Bundle
from agent_suite._variants import validate_variant
from test_documents import ROOT, content_fixture


@pytest.fixture
def bundle():
    return Bundle.from_bytes({p.name: p.read_bytes() for p in (ROOT / 'schema').glob('*.json')})


def bundled(bundle):
    content = content_fixture('rich-evaluations')
    provider = read_documents(content, bundle).providers[0].record
    return content, provider, provider.variants[0]


def dependency(key, digest):
    return ToolProviderDependency(key, '1.0.0', digest, source=Source('provider.json', '/variants/0/dependencies/0'))


def graph(provider, variant, edges):
    digests = {key: 'sha256:' + f'{i+1:064x}' for i, key in enumerate(edges)}
    result = {}
    for key, deps in edges.items():
        selected = replace(variant, variant_digest=digests[key],
                           dependencies=tuple(dependency(d, digests[d]) for d in deps))
        result[key+'@1.0.0'] = replace(provider, id=key, version='1.0.0', variants=(selected,))
    return result


def test_shared_bundle_cases(bundle):
    cases = json.loads((ROOT / 'testdata/conformance/bundle-cases.json').read_bytes())['cases']
    assert len(cases) == len({c['name'] for c in cases}) == 47
    assert Counter(c['scope'] for c in cases) == {'variant':29, 'closure':10, 'collision':8}
    assert sum(c.get('supportedFullPackage', False) for c in cases) == 20
    for case in cases:
        assert type(case['valid']) is bool
        content = Content()
        assert case['sourceType'] in ('directory', 'archive')
        content.source_type = 'directory' if case['sourceType'] == 'directory' else ''
        for entry in case['entries']:
            content.add(Entry(entry['path'], kind=entry['type'], mode=entry['mode'], uid=entry['uid'],
                              gid=entry['gid'], size=entry['size'], digest=entry['digest'], link_target=entry['linkTarget']))
        providers = {}
        try:
            for row in case['providers']:
                doc = Document(base64.b64decode(row['bytes'], validate=True), Source(row['file']))
                provider = read_document(doc, ToolProvider, bundle).record
                assert row['key'] == provider.id+'@'+provider.version
                providers[row['key']] = provider
            root = providers[case['rootKey']].variants[case['variant']]
            if case['scope'] == 'variant':
                validate_variant(root, content)
            else:
                selected = bundle_closure(case['rootKey'], root, providers)
                if case['scope'] == 'collision':
                    destinations = {}
                    for item in selected:
                        add_variant_destinations(destinations, item.variant)
                elif case['valid']:
                    assert [b.provider_key for b in selected] == case['order'], case['name']
        except DocumentError as error:
            assert not case['valid'], (case['name'], error)
            assert error.diagnostics[0].source.file
            assert error.diagnostics[0].code.startswith(('schema.', 'document.', 'variant.', 'bundle.'))
        else:
            assert case['valid'], case['name']


def test_bundled_native_directory_and_archive_authority(tmp_path, bundle):
    from agent_suite._directory import load_directory
    from agent_suite._oci import load_oci_layout
    from test_oci import materialize
    root = tmp_path / 'suite'
    shutil.copytree(ROOT / 'testdata/rich-evaluations', root)
    if os.name == 'nt':
        from _directory_windows_fixture import secure_fixture
        secure_fixture(root)
    content = load_directory(root)
    providers = read_documents(content, bundle).providers
    assert providers
    validate_bundles(content, {p.record.id+'@'+p.record.version: p.record for p in providers})
    layout = tmp_path / 'layout'
    materialize(layout, {'layout': 'inventory-mode-mismatch'})
    archive = load_oci_layout(layout)
    providers = read_documents(archive, bundle).providers
    assert providers
    with pytest.raises(DocumentError) as error:
        validate_bundles(archive, {p.record.id+'@'+p.record.version: p.record for p in providers})
    assert error.value.diagnostics[0].code == 'variant.metadata'


def test_private_variant_inventory_and_directory_modes(bundle):
    content, provider, variant = bundled(bundle)
    validate_bundles(content, {provider.id+'@'+provider.version: provider})
    for item in variant.files:
        assert content.entries[variant.payload_root+'/'+item.path].mode == item.mode
    assert digest_bytes(variant_bytes(variant.raw.value)) == variant.variant_digest
    assert variant.raw.source == variant.source


def test_directory_mode_binding_does_not_rewrite_archive_or_allow_conflicts(bundle):
    content, _, variant = bundled(bundle)
    entry = next(e for e in variant.files if e.type == 'file')
    path = variant.payload_root+'/'+entry.path
    content.bind_directory_mode(path, entry.mode)
    content.bind_directory_mode(path, entry.mode)
    with pytest.raises(ValueError, match='conflicting'):
        content.bind_directory_mode(path, entry.mode ^ 0o100)
    content.source_type = ''
    content.bind_directory_mode(path, 0o777)
    assert content.entries[path].mode == entry.mode
    content.entries[path] = replace(content.entries[path], mode=entry.mode ^ 0o100)
    with pytest.raises(DocumentError) as error:
        validate_variant(variant, content)
    assert error.value.diagnostics[0].code == 'variant.metadata'


def test_all_variants_bind_directory_modes_even_if_not_selected(bundle):
    content, provider, variant = bundled(bundle)
    entry = next(e for e in variant.files if e.type == 'file')
    changed = replace(variant, files=tuple(replace(e, mode=e.mode ^ 0o100) if e.path == entry.path else e
                                           for e in variant.files),
                      platform=replace(variant.platform, architecture='arm64'))
    with pytest.raises(DocumentError, match='conflicting'):
        validate_bundles(content, {provider.id+'@'+provider.version: replace(provider, variants=(variant, changed))})


def test_archive_mode_mismatch_missing_and_untracked_payload(bundle):
    for change, code in [('mode', 'variant.metadata'), ('missing', 'variant.missing'), ('extra', 'variant.untracked')]:
        content, _, variant = bundled(bundle)
        content.source_type = ''
        for item in variant.files:
            path = variant.payload_root+'/'+item.path
            content.entries[path] = replace(content.entries[path], mode=item.mode)
        file = next(e for e in variant.files if e.type == 'file')
        path = variant.payload_root+'/'+file.path
        if change == 'mode':
            content.entries[path] = replace(content.entries[path], mode=file.mode ^ 0o100)
        elif change == 'missing':
            del content.entries[path]
        else:
            content.add(replace(content.entries[path], path=variant.payload_root+'/unexpected'))
        with pytest.raises(DocumentError) as error:
            validate_variant(variant, content)
        assert error.value.diagnostics[0].code == code


def test_raw_variant_identity_does_not_serialize_defaulted_typed_fields(bundle):
    content, _, variant = bundled(bundle)
    assert digest_bytes(variant_bytes(variant.raw.value)) == variant.variant_digest
    with pytest.raises(DocumentError) as error:
        validate_variant(replace(variant, variant_digest='sha256:'+'0'*64), content)
    assert error.value.diagnostics[0].code == 'variant.digest'


def test_dependency_closure_exact_order_cycles_and_deep_chain(bundle):
    _, provider, variant = bundled(bundle)
    providers = graph(provider, variant, {'a': ['b', 'c'], 'b': ['d'], 'c': ['d'], 'd': []})
    result = bundle_closure('a@1.0.0', providers['a@1.0.0'].variants[0], providers)
    assert [b.provider_key for b in result] == ['a@1.0.0', 'b@1.0.0', 'd@1.0.0', 'c@1.0.0']
    cyclic = graph(provider, variant, {'a': ['b'], 'b': ['c'], 'c': ['a']})
    with pytest.raises(DocumentError) as error:
        bundle_closure('a@1.0.0', cyclic['a@1.0.0'].variants[0], cyclic)
    assert error.value.diagnostics[0].code == 'bundle.cycle'
    edges = {f'p{i}': [f'p{i+1}'] for i in range(1100)}
    edges['p1100'] = []
    deep = graph(provider, variant, edges)
    assert len(bundle_closure('p0@1.0.0', deep['p0@1.0.0'].variants[0], deep)) == 1101


def test_dependency_edge_is_checked_before_visited_reuse(bundle):
    _, provider, variant = bundled(bundle)
    providers = graph(provider, variant, {'a': ['b', 'c'], 'b': ['d'], 'c': ['d'], 'd': []})
    c = providers['c@1.0.0']
    cv = c.variants[0]
    providers['c@1.0.0'] = replace(c, variants=(replace(cv, dependencies=(dependency('d', 'sha256:'+'0'*64),)),))
    with pytest.raises(DocumentError) as error:
        bundle_closure('a@1.0.0', providers['a@1.0.0'].variants[0], providers)
    assert error.value.diagnostics[0].code == 'bundle.selection'


def test_collision_equality_ignores_path_and_component_but_not_metadata(bundle):
    _, _, variant = bundled(bundle)
    entry = next(e for e in variant.files if e.type == 'file')
    first = replace(variant, install_root='/opt/test', files=(replace(entry, path='bin/tool'),))
    second = replace(variant, install_root='/opt/test/bin', files=(replace(entry, path='tool', component='different'),))
    destinations = {}
    add_variant_destinations(destinations, first)
    add_variant_destinations(destinations, second)
    assert list(destinations) == ['/opt/test/bin/tool']
    for field, value in [('mode', entry.mode ^ 0o100), ('uid', 1), ('gid', 1), ('size', entry.size+1),
                         ('digest', 'sha256:'+'0'*64), ('type', 'hardlink'), ('link_target', 'other')]:
        with pytest.raises(DocumentError) as error:
            add_variant_destinations(dict(destinations), replace(second, files=(replace(second.files[0], **{field:value}),)))
        assert error.value.diagnostics[0].code == 'bundle.collision'
