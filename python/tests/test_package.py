"""Whole-package reader, resource ownership and authored typed views."""
import importlib
import importlib.util
import json
import shutil
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from agent_suite._json import canonical_bytes,digest_bytes
from test_capture import extracted,literal_fixture,packed_fixture,secure
from test_documents import ROOT


@pytest.fixture
def api(monkeypatch):
    assert importlib.util.find_spec('agent_suite._package') is not None, 'finished-reader module missing'
    module = importlib.import_module('agent_suite._package')
    # Source-tree tests supply the exact checkout bundle. Installed smoke tests
    # separately exercise the provenance-checked packaged assets without a mock.
    from agent_suite._schema import Bundle
    monkeypatch.setattr(module.Bundle,'installed',classmethod(lambda cls:Bundle.from_bytes(
        {p.name:p.read_bytes() for p in (ROOT/'schema').glob('*.json')})))
    return module


def rich(tmp_path):
    root = tmp_path/'rich'
    shutil.copytree(ROOT/'testdata/rich-evaluations',root)
    secure(root)
    return root


def test_package_rich_ordered_authored_views_and_identity(tmp_path,api):
    root = rich(tmp_path)
    raw = (root/'agentsuite.json').read_bytes()
    with api.Package.load(root) as package:
        assert list(package.agents) == ['writer']
        agent = package.agents['writer']
        assert agent.source.file == 'agents/writer.json'
        assert agent.instructions.reference.source.pointer == '/instructions'
        assert agent.evaluations is not None and agent.policy is not None
        expected_index = json.loads((root/'evals/writer/index.json').read_bytes())
        assert [c.declaration.id for c in agent.evaluations.cases] == [
            Path(ref['path']).stem for ref in expected_index['cases']]
        for case,ref in zip(agent.evaluations.cases,expected_index['cases']):
            original = json.loads((root/ref['path']).read_bytes())
            assert [a.kind for a in case.assertions] == [a['type'] for a in original['assertions']]
            assert case.document.data == (root/ref['path']).read_bytes()
            assert case.source.file == ref['path']
            assert [a.source.pointer for a in case.assertions] == [f'/assertions/{i}' for i in range(len(case.assertions))]
            assert case.declaration.runs == original.get('runs')
            assert case.declaration.min_passes == original.get('minPasses')
        assert package.root_digest == digest_bytes(canonical_bytes(json.loads(raw)))
        assert package.artifact_digest is None
        assert package.validate() == ()
        with pytest.raises(TypeError):
            package.agents['new'] = agent
        with pytest.raises(FrozenInstanceError):
            package.root_digest = 'unverified'


@pytest.mark.parametrize('oci', [False,True])
def test_package_self_contained_and_validate_never_reopens_source(tmp_path,api,monkeypatch,oci):
    root,bodies = extracted(tmp_path)
    if oci:
        layout = tmp_path/'layout'
        packed_fixture(root,layout)
        root = layout
    secure(root)
    package = api.Package(root)
    view = package.agents['writer'].instructions.content
    expected = bodies['instructions/writer.md']
    shutil.rmtree(root)
    def forbidden(*args, **kwargs):
        raise AssertionError('source was accessed after Package.load returned')
    monkeypatch.setattr(api,'load_directory',forbidden)
    monkeypatch.setattr(api,'load_oci_layout',forbidden)
    assert b''.join(view.iter_bytes()) == expected
    assert package.validate() == ()
    assert (package.artifact_digest is not None) == oci
    identity = package.root_digest
    package.close()
    package.close()
    assert package.root_digest == identity
    assert package.agents['writer'].declaration.id == 'writer'
    with pytest.raises(ValueError,match='closed'):
        package.validate()
    with pytest.raises(ValueError,match='closed'):
        next(view.iter_bytes())


def test_package_repr_and_equality_do_not_traverse_captured_content(tmp_path,api):
    root,_ = extracted(tmp_path)
    secure(root)
    with api.Package.load(root) as package:
        assert len(repr(package)) < 200
        assert '_content' not in repr(package)
        assert hash(package) == object.__hash__(package)
        assert package == package


def test_package_validate_rehashes_retained_literal_backing(tmp_path,api):
    root,_ = extracted(tmp_path)
    secure(root)
    with api.Package.load(root) as package:
        spool = package._snapshot._file
        assert spool is not None
        spool.seek(0)
        first = spool.read(1)
        spool.seek(0)
        spool.write(bytes([first[0]^1]))
        spool.flush()
        diagnostics = package.validate()
        assert [(d.code,d.source.file,d.source.pointer) for d in diagnostics] == [
            ('snapshot.pin','agents/writer.json','/instructions')]


def test_package_construction_failure_releases_captured_snapshot(tmp_path,api,monkeypatch):
    root = rich(tmp_path)
    capture = api.capture_directory
    snapshots = []
    def tracked(*args):
        snapshot = capture(*args)
        snapshots.append(snapshot)
        return snapshot
    def fail_view(value):
        raise RuntimeError('view construction failed')
    monkeypatch.setattr(api,'capture_directory',tracked)
    monkeypatch.setattr(api,'_evaluation_view',fail_view)
    with pytest.raises(RuntimeError,match='view construction failed'):
        api.Package.load(root)
    assert len(snapshots) == 1 and snapshots[0].closed


def test_package_context_failure_closes_snapshot_and_discards_private_content(tmp_path,api):
    root,_ = extracted(tmp_path)
    secure(root)
    package = api.Package.load(root)
    with pytest.raises(RuntimeError):
        with package:
            raise RuntimeError('caller failed')
    assert package._snapshot.closed
    assert not package._content.entries
    assert package.suite.record.name == 'example'


@pytest.mark.parametrize('path', ['', 'missing'])
def test_package_load_error_has_structured_diagnostics(tmp_path,api,monkeypatch,path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(api.LoadError) as error:
        api.Package.load(path)
    assert error.value.diagnostics and error.value.__cause__ is not None
    assert error.value.diagnostics[0].code.startswith('load.')


def test_package_root_can_be_noncanonical_but_pins_stay_verified(tmp_path,api):
    root,_ = extracted(tmp_path)
    value = json.loads((root/'agentsuite.json').read_bytes())
    raw = json.dumps(value,indent=2).encode()+b'\n'
    (root/'agentsuite.json').write_bytes(raw)
    secure(root)
    with api.Package.load(root) as package:
        assert package.suite.document.data == raw
        assert package.root_digest == digest_bytes(canonical_bytes(value))
    (root/'instructions/writer.md').write_bytes(b'changed')
    with pytest.raises(api.LoadError) as error:
        api.Package.load(root)
    assert error.value.diagnostics[0].code.startswith('pin.')


def test_package_empty_pathlike_refused_from_valid_package_directory(tmp_path,api,monkeypatch):
    root,_ = extracted(tmp_path)
    secure(root)
    monkeypatch.chdir(root)
    class Empty:
        def __fspath__(self):
            return ''
    for path in ('',Empty()):
        with pytest.raises(api.LoadError) as error:
            api.Package.load(path)
        assert error.value.diagnostics[0].code == 'load.content'


def test_package_marker_io_error_does_not_fall_back_to_directory(tmp_path,api,monkeypatch):
    root,_ = extracted(tmp_path)
    original = Path.lstat
    def marker_denied(path,*args,**kwargs):
        if path == root/'oci-layout':
            raise PermissionError('marker access denied')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'lstat',marker_denied)
    with pytest.raises(api.LoadError) as error:
        api.Package.load(root)
    assert error.value.diagnostics[0].code == 'load.io'
    assert isinstance(error.value.__cause__,PermissionError)


def test_package_marker_presence_is_not_silently_ignored(tmp_path,api):
    root,_ = extracted(tmp_path)
    (root/'oci-layout').write_bytes(b'invalid layout marker')
    secure(root)
    with pytest.raises(api.LoadError):
        api.Package.load(root)


@pytest.mark.parametrize('oci',[False,True])
@pytest.mark.parametrize('row',json.loads((ROOT/'testdata/conformance/literal-cases.json').read_bytes())['cases'],
                         ids=lambda row:row['name'])
def test_package_shared_literal_bytes_outlive_source(tmp_path,api,oci,row):
    root,expected = literal_fixture(tmp_path,row)
    source = root
    if oci:
        source = tmp_path/'layout'
        packed_fixture(root,source)
    secure(source)
    with api.Package.load(source) as package:
        if row['target'] == 'instructions':
            view = package.agents['writer'].instructions
        else:
            views = [view for provider in package.tool_providers.values() for tool in provider.tools
                     for view in (tool.input_schema,tool.output_schema) if view is not None]
            view = next(view for view in views if view.reference.path==row['path'])
        shutil.rmtree(root)
        if oci:
            shutil.rmtree(source)
        assert b''.join(view.content.iter_bytes()) == expected
        assert package.root_digest == row['rootDigest']
        assert package.validate() == ()


def test_package_tool_schemas_and_policy_identity_survive_removal(tmp_path,api):
    root = rich(tmp_path)
    package = api.Package.load(root)
    schemas = [(tool.input_schema,(root/tool.input_schema.reference.path).read_bytes())
        for provider in package.tool_providers.values() for tool in provider.tools]
    policy = package.agents['writer'].policy
    assert policy is not None
    expected_policy = policy.document.data
    shutil.rmtree(root)
    with package:
        assert schemas
        for view,body in schemas:
            assert b''.join(view.content.iter_bytes()) == body
        assert policy.document.data == expected_policy
        assert policy.reference.descriptor.digest == digest_bytes(expected_policy)
        assert package.validate() == ()
