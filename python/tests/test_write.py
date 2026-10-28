"""Public identities, transactional instruction edits and fresh package output."""
import gzip
import hashlib
import io
import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

import agent_suite as sdk
from agent_suite._json import canonical_bytes, decode, digest_bytes
from test_capture import extracted, literal_fixture, packed_fixture, secure
from test_documents import ROOT
from test_package import api, rich


@pytest.fixture(autouse=True)
def trusted_output_parent(tmp_path):
    secure(tmp_path)


def contents(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


def test_public_identity_domains():
    assert sdk.canonical_bytes({'b': -0.0, 'a': 1e-6}) == b'{"a":0.000001,"b":0}'
    assert sdk.digest({}) == 'sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a'
    value = {'variantDigest': 'old', 'nested': {'variantDigest': 'keep'}}
    expected = b'{"nested":{"variantDigest":"keep"},"variantDigest":""}'
    assert sdk.variant_digest(value) == 'sha256:' + hashlib.sha256(expected).hexdigest()
    assert value['variantDigest'] == 'old'
    from types import MappingProxyType
    assert sdk.canonical_bytes(MappingProxyType({'a': (1, 2)})) == b'{"a":[1,2]}'
    assert sdk.digest(MappingProxyType({})) == sdk.digest({})
    assert sdk.oci_manifest_digest(b'{ }\n') != sdk.digest({})
    assert sdk.oci_manifest_digest(b'{ }\n') == 'sha256:' + hashlib.sha256(b'{ }\n').hexdigest()


@pytest.mark.parametrize('name', ['minimal', 'remote', 'bundled', 'runtime-two-profiles', 'rich'])
@pytest.mark.parametrize('method', ['write_directory', 'write_oci'])
def test_write_roundtrip_and_repeat(tmp_path, api, name, method):
    root = rich(tmp_path) if name == 'rich' else extracted(tmp_path, name)[0]
    secure(root)
    with api.Package(root) as package:
        before = package.root_digest
        one, two = tmp_path/'one', tmp_path/'two'
        assert getattr(package, method)(one) == one
        assert getattr(package, method)(two) == two
        assert contents(one) == contents(two)
        with api.Package(one) as loaded:
            assert loaded.root_digest == before
            assert loaded.validate() == ()
            assert loaded.agents['writer'].instructions.reference == package.agents['writer'].instructions.reference


def test_instruction_edit_copy_on_write_and_rollback(tmp_path, api):
    root, bodies = extracted(tmp_path)
    secure(root)
    with api.Package(root) as package:
        original = package.agents['writer']
        identity = package.root_digest
        package.set_instructions('writer', b'new\xffinstructions')
        view = package.agents['writer']
        assert view.instructions.reference.path != original.instructions.reference.path
        assert b''.join(view.instructions.content.iter_bytes()) == b'new\xffinstructions'
        with pytest.raises(UnicodeDecodeError):
            ''.join(view.instructions.content.iter_text())
        assert package.root_digest != identity
        assert package.artifact_digest is None and package.validate() == ()
        state = package.root_digest
        for agent, body in [('unknown', b'x'), ('writer', 42), ('writer', '\ud800')]:
            with pytest.raises((ValueError, TypeError, KeyError)):
                package.set_instructions(agent, body)
            assert package.root_digest == state and package.validate() == ()
        shutil.rmtree(root)
        out = package.write_directory(tmp_path/'edited')
        assert (out/original.instructions.reference.path).read_bytes() == bodies[original.instructions.reference.path]
        with api.Package(out) as again:
            assert b''.join(again.agents['writer'].instructions.content.iter_bytes()) == b'new\xffinstructions'
        package.set_instructions('writer', 'second edit')
        assert b''.join(package.agents['writer'].instructions.content.iter_bytes()) == b'second edit'
        assert package.validate() == ()


def test_stale_graph_is_never_repaired(tmp_path, api):
    root, _ = extracted(tmp_path)
    secure(root)
    with api.Package(root) as package:
        entry = package._content.entries['agents/writer.json']
        package._content.entries[entry.path] = replace(entry, digest='sha256:'+'0'*64)
        for action in (lambda: package.set_instructions('writer', 'x'),
                       lambda: package.write_directory(tmp_path/'bad'),
                       lambda: package.write_oci(tmp_path/'bad')):
            with pytest.raises((ValueError, api.LoadError)):
                action()
        assert not (tmp_path/'bad').exists()


@pytest.mark.parametrize('method', ['write_directory', 'write_oci'])
def test_write_closed_and_existing_destination(tmp_path, api, method):
    root, _ = extracted(tmp_path)
    secure(root)
    package = api.Package(root)
    dest = tmp_path/'existing'
    dest.mkdir()
    (dest/'keep').write_bytes(b'keep')
    with pytest.raises((ValueError, OSError, api.LoadError)):
        getattr(package, method)(dest)
    assert (dest/'keep').read_bytes() == b'keep'
    package.close()
    for action in (lambda: getattr(package, method)(tmp_path/'closed'),
                   lambda: package.set_instructions('writer', 'x')):
        with pytest.raises(ValueError, match='closed'):
            action()
    assert not (tmp_path/'closed').exists()


def test_unchanged_oci_preserves_noncanonical_manifest_bytes(tmp_path, api):
    root, _ = extracted(tmp_path)
    layout = tmp_path/'layout'
    packed_fixture(root, layout)
    blobs = layout/'blobs/sha256'
    index = decode((layout/'index.json').read_bytes())
    descriptor = index['manifests'][0]
    manifest = (blobs/descriptor['digest'][7:]).read_bytes()
    raw = b' \n'+manifest+b'\n'
    (blobs/digest_bytes(raw)[7:]).write_bytes(raw)
    descriptor.update(size=len(raw), digest=digest_bytes(raw))
    index_raw = b'\n'+canonical_bytes(index)+b' '
    (layout/'index.json').write_bytes(index_raw)
    secure(layout)
    with api.Package(layout) as package:
        out = package.write_oci(tmp_path/'copy')
        for path, data in contents(out).items():
            assert (layout/path).read_bytes() == data
        # Unreferenced stale fixture blobs need not be copied; selected blobs do.
        original_manifest = decode(raw)
        for descriptor in [descriptor, original_manifest['config'], *original_manifest['layers']]:
            path = 'blobs/sha256/'+descriptor['digest'][7:]
            assert (out/path).read_bytes() == (layout/path).read_bytes()
        assert (out/'index.json').read_bytes() == index_raw
        assert (out/'blobs/sha256'/digest_bytes(raw)[7:]).read_bytes() == raw
        with api.Package(out) as loaded:
            assert loaded.artifact_digest == package.artifact_digest
        package.set_instructions('writer', 'edited OCI')
        assert package.artifact_digest is None
        with api.Package(package.write_oci(tmp_path/'changed')) as loaded:
            assert loaded.root_digest == package.root_digest
            assert loaded.artifact_digest != digest_bytes(raw)


@pytest.mark.parametrize('missing', [False, True])
def test_missing_or_changed_arbitrary_payload_refused_and_cleaned(tmp_path, api, missing):
    root, _ = extracted(tmp_path)
    (root/'payload.bin').write_bytes(b'arbitrary binary')
    secure(root)
    with api.Package(root) as package:
        if missing:
            (root/'payload.bin').unlink()
        else:
            (root/'payload.bin').write_bytes(b'changed payload!')
        for method in ('write_directory', 'write_oci'):
            dest = tmp_path/method
            with pytest.raises((OSError, ValueError, api.LoadError), match='payload|source|write'):
                getattr(package, method)(dest)
            assert not dest.exists()
        assert package.validate() == ()


def repin(root, reference, value):
    data = canonical_bytes(value)
    target = root/reference['path']
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    reference['descriptor'].update(size=len(data), digest=digest_bytes(data))


def test_edit_shared_agent_and_provider_literal_aliases(tmp_path, api):
    root, _ = extracted(tmp_path, 'remote')
    secure(root)
    with api.Package(root) as loaded:
        schema = next(iter(loaded.tool_providers.values())).tools[0].input_schema.reference
    suite = decode((root/'agentsuite.json').read_bytes())
    writer_ref = suite['agents'][0]
    writer = decode((root/writer_ref['path']).read_bytes())
    writer['instructions'].update(path=schema.path)
    writer['instructions']['descriptor'].update(size=schema.descriptor.size, digest=schema.descriptor.digest)
    repin(root, writer_ref, writer)
    other_ref = decode(canonical_bytes(writer_ref))
    other_ref.update(id='other', path='agents/other.json')
    other = decode(canonical_bytes(writer))
    other['id'] = 'other'
    repin(root, other_ref, other)
    suite['agents'].append(other_ref)
    composition_ref = decode(canonical_bytes(suite['compositions'][0]))
    composition = decode((root/composition_ref['path']).read_bytes())
    composition_ref.update(agent='other', path='compositions/other.json')
    composition['agent'] = 'other'
    repin(root, composition_ref, composition)
    suite['compositions'].append(composition_ref)
    (root/'agentsuite.json').write_bytes(canonical_bytes(suite))
    (root/'instructions/writer.md').unlink()  # No uncached, unreferenced binary in this fixture.
    secure(root)
    with api.Package(root) as package:
        provider = next(iter(package.tool_providers.values()))
        original = b''.join(provider.tools[0].input_schema.content.iter_bytes())
        old = package.agents['other'].document.data
        package.set_instructions('writer', 'chosen only')
        assert package.agents['other'].document.data == old
        assert b''.join(package.agents['other'].instructions.content.iter_bytes()) == original
        provider = next(iter(package.tool_providers.values()))
        assert b''.join(provider.tools[0].input_schema.content.iter_bytes()) == original
        shutil.rmtree(root)
        for method in ('write_directory', 'write_oci'):
            with api.Package(getattr(package, method)(tmp_path/method)) as again:
                assert b''.join(again.agents['other'].instructions.content.iter_bytes()) == original
                assert b''.join(again.agents['writer'].instructions.content.iter_bytes()) == b'chosen only'


@pytest.mark.parametrize('row', json.loads((ROOT/'testdata/conformance/literal-cases.json').read_bytes())['cases'],
                         ids=lambda r: r['name'])
def test_writer_large_and_non_utf8_literals_outlive_source(tmp_path, api, row):
    root, expected = literal_fixture(tmp_path, row)
    if row['target'] == 'instructions' and row['path'] != 'instructions/writer.md':
        (root/'instructions/writer.md').unlink()
    secure(root)
    with api.Package(root) as package:
        shutil.rmtree(root)
        for method in ('write_directory', 'write_oci'):
            output = getattr(package, method)(tmp_path/method)
            with api.Package(output) as loaded:
                views = [loaded.agents['writer'].instructions]
                views += [v for p in loaded.tool_providers.values() for t in p.tools
                          for v in (t.input_schema, t.output_schema) if v is not None]
                view = next(v for v in views if v.reference.path == row['path'])
                assert b''.join(view.content.iter_bytes()) == expected


@pytest.mark.parametrize('oci', [False, True])
def test_writer_missing_payload_above_json_bound(tmp_path, api, oci):
    root, _ = extracted(tmp_path)
    payload = bytes([0, 255, 122]) * ((4 << 20)//3+2)
    (root/'payload.bin').write_bytes(payload)
    source = root
    if oci:
        source = tmp_path/'layout'
        packed_fixture(root, source)
    secure(source)
    with api.Package(source) as package:
        assert package._content.entries['payload.bin'].data is None
        package.set_instructions('writer', 'edit while retaining arbitrary payload')
        output = package.write_directory(tmp_path/'copy')
        assert (output/'payload.bin').read_bytes() == payload


def test_edit_failure_transaction_and_stale_old_handles(tmp_path, api, monkeypatch):
    from agent_suite import _edit
    root, _ = extracted(tmp_path)
    secure(root)
    with api.Package(root) as package:
        view = package.agents['writer'].instructions.content
        old_body = b''.join(view.iter_bytes())
        old_digest = package.root_digest
        original = _edit.read_graph
        def fail(*args):
            raise OSError('injected candidate validation failure')
        monkeypatch.setattr(_edit, 'read_graph', fail)
        with pytest.raises(OSError, match='injected'):
            package.set_instructions('writer', 'new')
        assert package.root_digest == old_digest
        assert b''.join(view.iter_bytes()) == old_body and package.validate() == ()
        monkeypatch.setattr(_edit, 'read_graph', original)
        package.set_instructions('writer', 'new')
        with pytest.raises(ValueError, match='closed'):
            next(view.iter_bytes())


def test_write_cached_metadata_and_literals_ignore_changed_source(tmp_path, api):
    root, original = extracted(tmp_path)
    secure(root)
    with api.Package(root) as package:
        for path in original:
            (root/path).write_bytes(b'changed source')
        out = package.write_directory(tmp_path/'cached')
        assert contents(out) == original


@pytest.mark.parametrize('failure', ['short', 'zero', 'none', 'io'])
def test_write_short_writes_complete_or_clean_up(tmp_path, api, monkeypatch, failure):
    from agent_suite import _write
    root, _ = extracted(tmp_path)
    secure(root)
    with api.Package(root) as package:
        write = os.write
        def injected(fd, body):
            if failure == 'short':
                return write(fd, body[:7])
            if failure == 'zero':
                return 0
            if failure == 'none':
                return None
            raise OSError('injected disk failure')
        monkeypatch.setattr(_write.os, 'write', injected)
        dest = tmp_path/'output'
        if failure == 'short':
            package.write_directory(dest)
            with api.Package(dest) as loaded:
                assert loaded.root_digest == package.root_digest
        else:
            with pytest.raises(ValueError, match='short write|injected disk failure'):
                package.write_directory(dest)
            assert not dest.exists()
        assert package.validate() == ()


def test_source_oci_changed_is_refused_without_affecting_reader(tmp_path, api):
    root, _ = extracted(tmp_path)
    source = tmp_path/'layout'
    packed_fixture(root, source)
    secure(source)
    with api.Package(source) as package:
        index = decode((source/'index.json').read_bytes())
        index['manifests'][0]['digest'] = 'sha256:'+'0'*64
        (source/'index.json').write_bytes(canonical_bytes(index))
        with pytest.raises(ValueError, match='source OCI artifact changed'):
            package.write_oci(tmp_path/'bad')
        assert not (tmp_path/'bad').exists()
        assert package.validate() == ()


def test_writer_new_root_passes_native_security_checks(tmp_path, api):
    from agent_suite._directory import Native, _fd
    root, _ = extracted(tmp_path)
    secure(root)
    with api.Package(root) as package:
        for method in ('write_directory', 'write_oci'):
            output = getattr(package, method)(tmp_path/method)
            native = Native()
            def check_tree(parent, directory):
                for path in directory.iterdir():
                    with _fd(native.open_child(parent, path.name, path.is_dir())) as child:
                        native.check(child, root=path.is_dir())
                        if path.is_dir():
                            check_tree(child, path)
            with _fd(native.open_root(output)) as fd:
                native.check(fd, root=True)
                check_tree(fd, output)


def test_writer_retains_output_descriptors_until_completion(tmp_path, api, monkeypatch):
    from agent_suite import _write
    root, _ = extracted(tmp_path)
    secure(root)
    directory = _write._directory
    handles = []
    def checked(output, *args):
        assert os.fstat(output.fd)
        assert os.fstat(output.parent)
        handles.extend((output.fd, output.parent))
        directory(output, *args)
    monkeypatch.setattr(_write, '_directory', checked)
    with api.Package(root) as package:
        package.write_directory(tmp_path/'output')
        assert package.validate() == ()
    assert len(handles) == 2
    for fd in handles:
        with pytest.raises(OSError):
            os.fstat(fd)


def test_writer_mode_authority_and_links(tmp_path, api):
    root, _ = extracted(tmp_path, 'bundled')
    secure(root)
    if os.name == 'posix':
        (root/'unused-link').symlink_to('instructions/writer.md')
    with api.Package(root) as package:
        output = package.write_directory(tmp_path/'modes')
        for path, entry in package._content.entries.items():
            if entry.kind == 'file' and os.name == 'posix':
                assert (output/path).stat().st_mode & 0o777 == entry.mode
        if os.name == 'posix':
            assert os.readlink(output/'unused-link') == 'instructions/writer.md'
        with api.Package(package.write_oci(tmp_path/'archive')) as loaded:
            assert loaded.root_digest == package.root_digest
            if os.name == 'posix':
                assert loaded._content.entries['unused-link'].kind == 'symlink'


def test_writer_dest_symlink_and_parent_alias_are_refused(tmp_path, api):
    if os.name != 'posix':
        return
    root, _ = extracted(tmp_path)
    secure(root)
    (tmp_path/'alias').symlink_to(root, target_is_directory=True)
    with api.Package(root) as package:
        for dest in (tmp_path/'alias', tmp_path/'alias'/'nested'):
            with pytest.raises(ValueError, match='exist|link'):
                package.write_directory(dest)
        assert not (root/'nested').exists()


def test_writer_long_pax_paths_and_safe_hardlinks(tmp_path, api):
    from agent_suite._content import Entry
    root, _ = extracted(tmp_path)
    long_path = '/'.join(['long-directory-'+'x'*65]*4)+'/file.bin'
    (root/long_path).parent.mkdir(parents=True)
    (root/long_path).write_bytes(b'long path payload')
    secure(root)
    with api.Package(root) as package:
        # Model a safe ordinary hardlink as retained by the real OCI reader.
        package._content.add(Entry('hardlink', kind='hardlink', link_target=long_path))
        layout = package.write_oci(tmp_path/'pax')
        with api.Package(layout) as loaded:
            assert loaded._content.entries[long_path].digest == digest_bytes(b'long path payload')
            assert loaded._content.entries['hardlink'].kind == 'hardlink'
            if os.name == 'posix':
                output = loaded.write_directory(tmp_path/'linked')
                assert os.path.samefile(output/'hardlink', output/long_path)


def test_edit_preserves_authored_presence_and_unrelated_raw_documents(tmp_path, api):
    root, _ = extracted(tmp_path)
    suite = decode((root/'agentsuite.json').read_bytes())
    suite['extensions'] = [{'name': 'custom', 'critical': False}]
    (root/'agentsuite.json').write_bytes(b'\n'+canonical_bytes(suite)+b' ')
    secure(root)
    with api.Package(root) as package:
        profile = package.build_profiles[0].document.data
        catalog_size = package.suite.document.value['toolProviderCatalog']['descriptor']['size'].lexeme
        package.set_instructions('writer', 'changed')
        assert package.build_profiles[0].document.data == profile
        assert package.suite.document.value['extensions'][0]['critical'] is False
        assert package.suite.document.value['toolProviderCatalog']['descriptor']['size'].lexeme == catalog_size
        assert 'runtimeProfiles' not in package.suite.document.value
        assert sdk.digest(package.suite.document.value) == package.root_digest


@pytest.mark.parametrize('bound', ['regular', 'retained'])
def test_edit_checks_aggregate_bounds_after_repin_and_rolls_back(tmp_path, api, monkeypatch, bound):
    from agent_suite import _content, _edit
    root, _ = extracted(tmp_path)
    secure(root)
    with api.Package(root) as package:
        identity = package.root_digest
        old = package.agents['writer'].instructions.content
        if bound == 'regular':
            body = b'x'*10000
            total = sum(e.size for e in package._content.entries.values() if e.kind == 'file')
            monkeypatch.setattr(_edit, 'MAX_CONTENT_BYTES', total+len(body))
        else:
            body = b'x'*10000
            total = sum(e.size for e in package._content.entries.values()
                        if e.kind == 'file' and _content.retains(e.path, e.size))
            monkeypatch.setattr(_content, 'MAX_RETAINED_BYTES', total)
        with pytest.raises(ValueError, match='bound|limit'):
            package.set_instructions('writer', body)
        assert package.root_digest == identity and package.validate() == ()
        assert b''.join(old.iter_bytes())


def test_edit_committed_state_survives_old_spool_close_error(tmp_path, api, monkeypatch):
    root, _ = extracted(tmp_path)
    secure(root)
    with api.Package(root) as package:
        snapshot = package._snapshot
        original_close = snapshot.close
        def close_error():
            original_close()
            raise OSError('injected old snapshot reclamation failure')
        monkeypatch.setattr(snapshot, 'close', close_error)
        package.set_instructions('writer', 'committed')
        assert b''.join(package.agents['writer'].instructions.content.iter_bytes()) == b'committed'
        assert package.validate() == ()


@pytest.mark.parametrize('chunk_size', [3 << 20, 128 << 10, 17 << 10])
def test_fixed_gzip_store_large_sha_and_partitioning(chunk_size):
    from agent_suite._write import _GzipStore
    body = bytes(range(256))*12288
    output = io.BytesIO()
    writer = _GzipStore(output)
    for offset in range(0, len(body), chunk_size):
        assert writer.write(body[offset:offset+chunk_size]) == min(chunk_size, len(body)-offset)
    writer.finish()
    raw = output.getvalue()
    assert len(raw) == 3145991
    assert hashlib.sha256(raw).hexdigest() == 'cc35249d6ac85e8f8dde4c355be2db026f947b2caf6cbecfde8e055a1a70f231'
    assert gzip.decompress(raw) == body


@pytest.mark.parametrize('body,golden', [
    (b'', '1f8b08000000000000ff010000ffff0000000000000000'),
    (b'abc', '1f8b08000000000000ff010300fcff616263c241243503000000'),
])
def test_fixed_gzip_store_small_goldens(body, golden):
    from agent_suite._write import _GzipStore
    output = io.BytesIO()
    writer = _GzipStore(output)
    writer.write(body)
    writer.finish()
    assert output.getvalue().hex() == golden


@pytest.mark.parametrize('size', [65534, 65535, 65536, 131070])
def test_fixed_gzip_store_block_boundaries(size):
    from agent_suite._write import _GzipStore
    body = b'x'*size
    results = []
    for chunk_size in (size, 17 << 10):
        output = io.BytesIO()
        writer = _GzipStore(output)
        for offset in range(0, size, chunk_size):
            writer.write(body[offset:offset+chunk_size])
        writer.finish()
        results.append(output.getvalue())
    assert results[0] == results[1]
    assert gzip.decompress(results[0]) == body


def readonly_link_fixture(tmp_path):
    root, _ = extracted(tmp_path, 'bundled')
    suite = decode((root/'agentsuite.json').read_bytes())
    catalog_ref = suite['toolProviderCatalog']
    catalog = decode((root/catalog_ref['path']).read_bytes())
    provider_ref = catalog['toolProviders'][0]
    provider = decode((root/provider_ref['path']).read_bytes())
    variant = provider['variants'][0]
    variant['files'].extend([
        dict(path='links', type='directory', mode=0o555, uid=0, gid=0, component='large'),
        dict(path='links/tool', type='symlink', mode=0o777, uid=0, gid=0,
             component='large', linkTarget='../bin/tool-0000'),
    ])
    variant['files'].sort(key=lambda entry: entry['path'])
    variant['variantDigest'] = sdk.variant_digest(variant)
    repin(root, provider_ref, provider)
    repin(root, catalog_ref, catalog)
    composition_ref = suite['compositions'][0]
    composition = decode((root/composition_ref['path']).read_bytes())
    composition['toolProviders'][0].update(
        manifestDigest=provider_ref['descriptor']['digest'], variantDigest=variant['variantDigest'])
    repin(root, composition_ref, composition)
    (root/'agentsuite.json').write_bytes(canonical_bytes(suite))
    directory = root/variant['payloadRoot']/'links'
    directory.mkdir()
    (directory/'tool').symlink_to('../bin/tool-0000')
    directory.chmod(0o555)
    secure(root)
    return root, directory.relative_to(root)


def test_writer_readonly_inventory_directory_with_link(tmp_path, api):
    if os.name != 'posix':
        return
    root, relative = readonly_link_fixture(tmp_path)
    output = tmp_path/'readonly'
    try:
        with api.Package(root) as package:
            assert package.validate() == ()
            package.write_directory(output)
            assert (output/relative).stat().st_mode & 0o777 == 0o555
            assert os.readlink(output/relative/'tool') == '../bin/tool-0000'
            with api.Package(output) as loaded:
                assert loaded.validate() == ()
    finally:
        (root/relative).chmod(0o700)
        if (output/relative).exists():
            (output/relative).chmod(0o700)


def test_writer_cleanup_after_final_modes_preserves_original_error(tmp_path, api, monkeypatch):
    if os.name != 'posix':
        return
    from agent_suite import _write
    root, relative = readonly_link_fixture(tmp_path)
    output = tmp_path/'failed'
    directory = _write._directory
    def fail_after_modes(*args):
        directory(*args)
        (args[0].path/'outside').symlink_to(root, target_is_directory=True)
        (args[0].path/relative).chmod(0)
        raise RuntimeError('original post-mode failure')
    monkeypatch.setattr(_write, '_directory', fail_after_modes)
    try:
        with api.Package(root) as package:
            with pytest.raises(RuntimeError, match='original post-mode failure'):
                package.write_directory(output)
            assert not output.exists()
            assert (root/relative).stat().st_mode & 0o777 == 0o555
            assert package.validate() == ()
    finally:
        (root/relative).chmod(0o700)
        if (output/relative).exists():
            (output/relative).chmod(0o700)


def test_writer_cleanup_removes_readonly_files(tmp_path, api, monkeypatch):
    from agent_suite import _write
    root, _ = extracted(tmp_path)
    (root/'readonly.bin').write_bytes(b'readonly payload')
    modes = {p.relative_to(root).as_posix():
             (0o755 if p.is_dir() else 0o444 if p.name == 'readonly.bin' else 0o644)
             for p in root.rglob('*')}
    layout = tmp_path/'layout'
    packed_fixture(root, layout, modes)
    secure(layout)
    directory = _write._directory
    def fail_after_files(*args):
        directory(*args)
        assert not (args[0].path/'readonly.bin').stat().st_mode & 0o200
        raise RuntimeError('post-write test failure')
    monkeypatch.setattr(_write, '_directory', fail_after_files)
    with api.Package(layout) as package:
        with pytest.raises(RuntimeError, match='post-write test failure'):
            package.write_directory(tmp_path/'failed')
        assert not (tmp_path/'failed').exists()
        assert package.validate() == ()


@pytest.mark.parametrize('method', ['write_directory', 'write_oci'])
def test_writer_dotdot_destination_resolves_checked_parent(tmp_path, api, method):
    from agent_suite._write import _parent_path
    root, _ = extracted(tmp_path)
    secure(root)
    (tmp_path/'a').mkdir()
    destination = tmp_path/'a'/'..'/method
    with api.Package(root) as package:
        assert getattr(package, method)(destination) == destination
        with api.Package(destination) as loaded:
            assert loaded.root_digest == package.root_digest
    assert _parent_path(destination).parent == tmp_path.resolve()
    assert '..' not in _parent_path(destination).parts


def test_repeated_edits_bound_created_history_and_preserve_original_files(tmp_path, api):
    root, original = extracted(tmp_path)
    secure(root)
    with api.Package(root) as package:
        count = len(package._content.entries)
        size = sum(e.size for e in package._content.entries.values() if e.kind == 'file')
        original_path = package.agents['writer'].instructions.reference.path
        for index in range(20):
            body = f'{index:02d}'.encode()*2048
            package.set_instructions('writer', body)
        assert len(package._content.entries) == count+1
        assert sum(e.size for e in package._content.entries.values()
                   if e.kind == 'file') <= size+len(body)+512
        assert package._created_instruction_paths == frozenset({
            package.agents['writer'].instructions.reference.path})
        assert set(package._snapshot._ranges) == {
            original_path, package.agents['writer'].instructions.reference.path}
        shutil.rmtree(root)
        output = package.write_directory(tmp_path/'history')
        for path, data in original.items():
            if path not in ('agentsuite.json', 'agents/writer.json'):
                assert (output/path).read_bytes() == data
        assert (output/package.agents['writer'].instructions.reference.path).read_bytes() == body


def test_failed_history_edit_keeps_content_snapshot_and_owned_paths(tmp_path, api, monkeypatch):
    from agent_suite import _edit
    root, _ = extracted(tmp_path)
    secure(root)
    with api.Package(root) as package:
        package.set_instructions('writer', 'first')
        before = (package._content, package._snapshot, package.root_digest,
                  package._created_instruction_paths)
        entries = dict(package._content.entries)
        folded = dict(package._content._folded)
        def fail(*args):
            raise OSError('candidate history failure')
        monkeypatch.setattr(_edit, 'read_graph', fail)
        with pytest.raises(OSError, match='candidate history failure'):
            package.set_instructions('writer', 'second')
        assert (package._content, package._snapshot, package.root_digest,
                package._created_instruction_paths) == before
        assert package._content.entries == entries and package._content._folded == folded
        assert b''.join(package.agents['writer'].instructions.content.iter_bytes()) == b'first'
        assert not package._snapshot.closed and package.validate() == ()
