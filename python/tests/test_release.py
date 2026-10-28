import hashlib
import importlib.util
import io
import json
import tarfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_documents import ROOT


@pytest.fixture
def release():
    path = ROOT/'scripts/check-python-release.py'
    assert path.is_file(), 'missing Python release qualification helper'
    spec = importlib.util.spec_from_file_location('python_release', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def candidate(tmp_path, monkeypatch, release):
    sdk, contract, catalog = (tmp_path/name for name in ('sdk', 'contract', 'catalog'))
    sdk_sha, contract_sha, catalog_sha = '1'*40, '2'*40, '3'*40
    schemas = {p.name: p.read_bytes().replace(b'/schema/draft/', b'/schema/v0.8/') for p in (ROOT/'schema').glob('*.schema.json')}
    inventory = {name: {'id': json.loads(data)['$id'], 'sha256': hashlib.sha256(data).hexdigest()} for name, data in schemas.items()}
    provenance = {'schemaRevision': sdk_sha, 'schemas': {name: {'id': row['id'], 'digest': 'sha256:'+row['sha256']} for name, row in inventory.items()}}
    for repo in (sdk, contract, catalog):
        (repo/'schema').mkdir(parents=True)
        for name, data in schemas.items():
            (repo/'schema'/name).write_bytes(data)
    entry = {'path': 'v0.8', 'release': 'v0.8.0', 'sourceCommit': contract_sha,
             'assetUrl': 'https://github.com/agent-primitives/suite/releases/download/v0.8.0/schemas-v0.8.0.json',
             'sha256': '4'*64, 'schemas': inventory}
    registry = {'version': 1, 'bundles': [entry], 'releases': {'v0.8.0': 'v0.8'}}
    # Catalog is intentionally later than both frozen tags; its current schema tree is draft.
    for name in schemas:
        (catalog/'schema'/name).write_bytes((ROOT/'schema'/name).read_bytes())
    (catalog/'docs').mkdir()
    (catalog/'docs/schema-catalog.json').write_text(json.dumps(registry))
    publication = tmp_path/'dist'
    publication.mkdir()
    wheel = publication/'agent_suite-0.1.0-py3-none-any.whl'
    derived = tmp_path/'derived.whl'
    sdist = publication/'agent_suite-0.1.0.tar.gz'

    def distributions(version='0.1.0', derived_provenance=None):
        metadata = f'Name: agent-suite\nVersion: {version}\n'
        for target in (wheel, derived):
            with zipfile.ZipFile(target, 'w') as archive:
                archive.writestr(f'agent_suite-{version}.dist-info/METADATA', metadata)
                for name, data in schemas.items():
                    archive.writestr('agent_suite/_schemas/'+name, data)
                archive.writestr('agent_suite/_schemas/provenance.json', json.dumps(derived_provenance if target == derived and derived_provenance is not None else provenance))
        with tarfile.open(sdist, 'w:gz') as archive:
            entries = {'PKG-INFO': metadata.encode(), '_schema_source/provenance.json': json.dumps(provenance).encode()}
            entries.update({'_schema_source/'+name: data for name, data in schemas.items()})
            for name, data in entries.items():
                info = tarfile.TarInfo(f'agent_suite-{version}/'+name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))

    distributions()
    tags = {'refs/tags/python/v0.1.0^{commit}': sdk_sha, 'refs/tags/v0.8.0^{commit}': contract_sha}

    def git(repo, *args):
        repo = Path(repo)
        if args == ('rev-parse', 'HEAD'):
            return {sdk: sdk_sha, contract: contract_sha, catalog: catalog_sha}[repo].encode()
        if args[0] == 'rev-parse':
            return tags[args[-1]].encode()
        if args[0] == 'show':
            ref, name = args[1].split(':', 1)
            if name == 'docs/schema-catalog.json':
                return (catalog/name).read_bytes()
            return (repo/name).read_bytes()
        raise AssertionError(args)

    monkeypatch.setattr(release, 'git', git)
    monkeypatch.setenv('AGENTSUITE_GO_ORACLE_ROOT', str(contract))
    options = SimpleNamespace(sdk_repo=sdk, contract_repo=contract, catalog_repo=catalog,
                              catalog_ref=catalog_sha, sdk_tag='python/v0.1.0', contract_tag='v0.8.0',
                              wheel=wheel, sdist=sdist, sdist_wheel=derived, out=tmp_path/'qualification.json')
    return SimpleNamespace(options=options, schemas=schemas, provenance=provenance,
                           inventory=inventory, distributions=distributions, tags=tags,
                           dist=publication, sdk=sdk, contract=contract, catalog=catalog)


@pytest.mark.parametrize('bad', ['development', 'development-tag', 'sdk-tag', 'contract-tag', 'retargeted-sdk', 'retargeted-contract'])
def test_python_release_rejects_development_or_wrong_tags(candidate, release, bad):
    options = candidate.options
    if bad == 'development':
        candidate.distributions(version='0.1.0.dev0')
    elif bad == 'development-tag':
        options.sdk_tag = 'python/v0.1.0.dev0'
    elif bad == 'sdk-tag':
        options.sdk_tag = 'python/main'
    elif bad == 'contract-tag':
        options.contract_tag = 'v0.7.0'
    elif bad == 'retargeted-sdk':
        candidate.tags['refs/tags/python/v0.1.0^{commit}'] = '9'*40
    else:
        candidate.tags['refs/tags/v0.8.0^{commit}'] = '9'*40
    with pytest.raises(ValueError):
        release.qualify(options)


@pytest.mark.parametrize('bad', ['schema', 'draft', 'catalog', 'oracle'])
def test_python_release_binds_exact_frozen_contract_and_schema_bytes(candidate, release, bad, monkeypatch):
    if bad == 'schema':
        path = candidate.sdk/'schema/suite.schema.json'
        path.write_bytes(path.read_bytes()+b'\n')
    elif bad == 'draft':
        for repo in (candidate.sdk, candidate.contract):
            path = repo/'schema/suite.schema.json'
            path.write_bytes(path.read_bytes().replace(b'/v0.8/', b'/draft/'))
    elif bad == 'catalog':
        (candidate.catalog/'docs/schema-catalog.json').write_text('{"version":1,"bundles":[],"releases":{}}')
    else:
        monkeypatch.setenv('AGENTSUITE_GO_ORACLE_ROOT', str(candidate.sdk))
    with pytest.raises(ValueError):
        release.qualify(candidate.options)


def test_python_release_checks_both_distribution_provenances(candidate, release):
    changed = dict(candidate.provenance, schemaRevision='9'*40)
    candidate.distributions(derived_provenance=changed)
    with pytest.raises(ValueError, match='provenance'):
        release.qualify(candidate.options)


def test_python_release_records_validator_and_artifact_identities(candidate, release):
    record = release.qualify(candidate.options)
    assert record['sdkRevision'] == '1'*40
    assert record['suiteRevision'] == record['validatorRevision'] == record['vectorsRevision'] == '2'*40
    assert record['catalogRevision'] == '3'*40
    assert record['schemas'] == candidate.inventory
    assert len(record['distributions']) == 2
    candidate.options.out.write_text(json.dumps(record))
    release.verify_artifacts(candidate.options.out, candidate.dist)
    candidate.options.wheel.write_bytes(b'changed')
    with pytest.raises(ValueError):
        release.verify_artifacts(candidate.options.out, candidate.dist)


@pytest.mark.parametrize('change', ['missing', 'extra', 'tampered'])
def test_python_release_rejects_downloaded_artifact_changes(candidate, release, change):
    candidate.options.out.write_text(json.dumps(release.qualify(candidate.options)))
    if change == 'missing':
        candidate.options.wheel.unlink()
    elif change == 'extra':
        (candidate.dist/'unqualified.whl').write_bytes(b'extra')
    else:
        candidate.options.sdist.write_bytes(b'changed')
    with pytest.raises(ValueError):
        release.verify_artifacts(candidate.options.out, candidate.dist)


def test_python_release_oracle_override_selects_build_and_run(tmp_path, tmp_path_factory, monkeypatch):
    import test_write_conformance as oracle
    selected = tmp_path/'frozen-contract'
    calls = []

    def run(*args, **kwargs):
        calls.append(kwargs['cwd'])
        return SimpleNamespace(returncode=0, stdout='--- PASS: TestPythonWriterOutput (0.01s)', stderr='')

    monkeypatch.setattr(oracle, 'ORACLE_ROOT', selected, raising=False)
    monkeypatch.setattr(oracle.subprocess, 'run', run)
    executable = oracle.writer_oracle.__wrapped__(tmp_path_factory)
    oracle.go_validate(executable, tmp_path, [{'valid': True}])
    assert calls == [selected, selected/'internal/artifact']


@pytest.mark.parametrize('module_name, function_name, needs_path, compiled', [
    ('test_codec', 'test_go_numeric_differential', False, False),
    ('test_directory', 'test_go_casefold_differential', False, False),
    ('test_archive_differential', 'test_go_archive_differential', True, True),
    ('test_oci_differential', 'test_go_oci_differential', True, True),
    ('test_regex', 'test_go_regex_differential', True, True),
])
def test_python_release_all_differentials_use_selected_contract(tmp_path, monkeypatch, module_name, function_name, needs_path, compiled):
    import importlib
    import subprocess
    module = importlib.import_module(module_name)
    selected = tmp_path/'frozen-contract'
    calls = []

    class Captured(Exception):
        pass

    def run(command, **kwargs):
        calls.append((command, kwargs['cwd']))
        if compiled and len(calls) == 1:
            return SimpleNamespace(returncode=0)
        raise Captured

    monkeypatch.setattr(module, 'ORACLE_ROOT', selected, raising=False)
    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(Captured):
        getattr(module, function_name)(tmp_path) if needs_path else getattr(module, function_name)()
    assert calls[0][1] == selected
    if compiled:
        assert calls[1][1] == selected or calls[1][1] == selected/'internal/artifact'
    else:
        source = Path(calls[0][0][2])
        assert (source if source.is_absolute() else selected/source).is_relative_to(selected)


def test_python_release_qualifies_frozen_vector_suite():
    workflow = (ROOT/'.github/workflows/python-release.yml').read_text()
    assert 'python -m pytest contract-source/python/tests -q' in workflow


def test_python_release_unmapped_maintenance_tag_refused(candidate, release):
    candidate.options.contract_tag = 'v0.8.1'
    candidate.tags['refs/tags/v0.8.1^{commit}'] = '2'*40
    with pytest.raises(ValueError, match='catalog'):
        release.qualify(candidate.options)


def test_python_release_accepts_frozen_maintenance_tags(candidate, release):
    # No main-ancestry restriction: exact canonical tags are the maintained authority.
    candidate.options.sdk_tag = 'python/v0.1.1'
    candidate.options.contract_tag = 'v0.8.1'
    candidate.tags.update({'refs/tags/python/v0.1.1^{commit}': '1'*40, 'refs/tags/v0.8.1^{commit}': '2'*40})
    catalog_path = candidate.catalog/'docs/schema-catalog.json'
    catalog = json.loads(catalog_path.read_bytes())
    catalog['releases']['v0.8.1'] = 'v0.8'
    catalog_path.write_text(json.dumps(catalog))
    candidate.distributions(version='0.1.1')
    for key in ('wheel', 'sdist'):
        previous = getattr(candidate.options, key)
        target = previous.with_name(previous.name.replace('0.1.0', '0.1.1'))
        previous.rename(target)
        setattr(candidate.options, key, target)
    assert release.qualify(candidate.options)['version'] == '0.1.1'
