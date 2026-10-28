"""Frozen writer identities and Go validation of actual Python output."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from test_capture import extracted, literal_fixture, secure
from test_documents import ROOT
from test_package import api
from test_reader_conformance import cases, materialize


CASES = json.loads((ROOT/'testdata/conformance/write-cases.json').read_bytes())['cases']


@pytest.fixture(scope='session')
def writer_oracle(tmp_path_factory):
    root = tmp_path_factory.mktemp('writer-oracle')
    executable = root/('oracle.exe' if os.name == 'nt' else 'oracle')
    subprocess.run(['go', 'test', '-c', '-o', str(executable), './internal/artifact'],
                   cwd=ROOT, check=True, capture_output=True, timeout=120)
    return executable


def go_validate(executable, root, rows):
    request = root/'write-oracle.json'
    request.write_text(json.dumps(rows), encoding='utf-8')
    completed = subprocess.run([str(executable), '-test.run=TestPythonWriterOutput', '-test.count=1', '-test.v'],
        cwd=ROOT/'internal/artifact', env={**os.environ, 'AGENTSUITE_WRITE_ORACLE': str(request)},
        text=True, capture_output=True, timeout=120)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert '--- PASS: TestPythonWriterOutput ' in completed.stdout, completed.stdout


def row(path, root_digest, artifact_digest=''):
    return dict(path=str(path), rootDigest=root_digest, artifactDigest=artifact_digest, valid=True)


def test_shared_write_case_population():
    assert len(CASES) == 5
    assert {r['name'] for r in CASES} == {'minimal', 'coordinator-workers', 'policy-binding', 'rich-evaluations', 'large-instructions'}
    for value in CASES:
        assert set(value) == {'name', 'path', 'rootDigest', 'artifactDigest'}
        assert value['path'] == ('literal:instructions-above-4mib' if value['name'] == 'large-instructions'
                                 else 'testdata/' + value['name'])
        assert all(value[key].startswith('sha256:') and len(value[key]) == 71
                   for key in ('rootDigest', 'artifactDigest'))


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['name'])
def test_shared_write_identities_and_go_outputs(tmp_path, api, writer_oracle, case):
    secure(tmp_path)
    if case['name'] == 'large-instructions':
        literals = json.loads((ROOT/'testdata/conformance/literal-cases.json').read_bytes())['cases']
        source, _ = literal_fixture(tmp_path, next(c for c in literals if c['name'] == 'instructions-above-4mib'))
    else:
        source = tmp_path/'source'
        shutil.copytree(ROOT/case['path'], source)
    secure(source)
    outputs = []
    with api.Package(source) as package:
        assert package.root_digest == case['rootDigest']
        directory = package.write_directory(tmp_path/'directory')
        layout = package.write_oci(tmp_path/'layout')
        outputs += [row(directory, case['rootDigest']), row(layout, case['rootDigest'], case['artifactDigest'])]
        with api.Package(layout) as archived:
            assert archived.artifact_digest == case['artifactDigest']
            copied = archived.write_oci(tmp_path/'copied')
            outputs.append(row(copied, case['rootDigest'], case['artifactDigest']))
        # A supported typed edit updates only its known chain, never arbitrary
        # stale input. Go checks the exact bytes that Python actually wrote.
        agent = next(iter(package.agents))
        package.set_instructions(agent, b'Writer conformance edit.\n')
        assert package.root_digest != case['rootDigest']
        edited = package.write_directory(tmp_path/'edited')
        edited_oci = package.write_oci(tmp_path/'edited-oci')
        outputs.append(row(edited, package.root_digest))
        with api.Package(edited_oci) as loaded:
            outputs.append(row(edited_oci, package.root_digest, loaded.artifact_digest))
    # The loader, not a second writer, must refuse a stale edited ancestor.
    stale = tmp_path/'stale'
    shutil.copytree(edited, stale)
    secure(stale)
    root = stale/'agentsuite.json'
    value = json.loads(root.read_bytes())
    value['agents'][0]['descriptor']['digest'] = 'sha256:' + '0'*64
    root.write_text(json.dumps(value), encoding='utf-8')
    outputs.append(dict(path=str(stale), rootDigest='', artifactDigest='', valid=False,
                        error='agent ' + value['agents'][0]['id'] + ' manifest digest mismatch'))
    go_validate(writer_oracle, tmp_path, outputs)


@pytest.mark.parametrize('name', ['remote', 'bundled', 'runtime-two-profiles'])
def test_go_writer_variant_payloads(tmp_path, api, writer_oracle, name):
    secure(tmp_path)
    source, _ = extracted(tmp_path, name)
    secure(source)
    outputs = []
    with api.Package(source) as package:
        directory = package.write_directory(tmp_path/'directory')
        layout = package.write_oci(tmp_path/'layout')
        outputs.append(row(directory, package.root_digest))
        with api.Package(layout) as loaded:
            outputs.append(row(layout, package.root_digest, loaded.artifact_digest))
    go_validate(writer_oracle, tmp_path, outputs)


def test_write_all_shared_reader_positives(tmp_path, api, writer_oracle):
    secure(tmp_path)
    positives = [c for c in cases() if c['valid']]
    assert len(positives) == 25
    outputs = []
    for i, case in enumerate(positives):
        source = tmp_path/f'source-{i}'
        materialize(source, case)
        secure(source)
        with api.Package(source) as package:
            directory = package.write_directory(tmp_path/f'dir-{i}')
            layout = package.write_oci(tmp_path/f'oci-{i}')
            outputs.append(row(directory, package.root_digest))
            with api.Package(layout) as loaded:
                outputs.append(row(layout, package.root_digest, loaded.artifact_digest))
    assert len(outputs) == 50
    go_validate(writer_oracle, tmp_path, outputs)
