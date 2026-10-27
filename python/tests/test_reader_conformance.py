"""Frozen complete Go packages through the public reader and real native backend."""
import base64
import json
import shutil

import pytest

from agent_suite._json import digest_bytes
from agent_suite._schema import Bundle
from test_capture import packed_fixture,secure
from test_documents import ROOT


DIAGNOSTICS = json.loads((ROOT/'python/tests/reader-diagnostics.json').read_bytes())


def assert_refusal(error,name):
    diagnostic = error.value.diagnostics[0]
    assert dict(code=diagnostic.code,file=diagnostic.source.file,pointer=diagnostic.source.pointer) == DIAGNOSTICS[name]


def cases():
    value = json.loads((ROOT/'testdata/conformance/reader-cases.json').read_bytes())
    assert set(value) == {'cases'} and len(value['cases']) == 30
    extra = json.loads((ROOT/'testdata/conformance/reader-semantic-cases.json').read_bytes())
    assert set(extra) == {'cases'} and len(extra['cases']) == 112
    return value['cases'] + extra['cases']


@pytest.fixture
def api(monkeypatch):
    from agent_suite import LoadError,Package
    bundle = Bundle.from_bytes({p.name:p.read_bytes() for p in (ROOT/'schema').glob('*.json')})
    monkeypatch.setattr(Bundle,'installed',classmethod(lambda cls:bundle))
    return Package,LoadError


def materialize(root,row):
    root.mkdir()
    for entry in row['entries']:
        path = root/entry['path']
        if entry['type'] == 'directory':
            path.mkdir(parents=True,exist_ok=True)
        else:
            assert entry['type'] == 'file'
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(base64.b64decode(entry['bytes'],validate=True))
        path.chmod(entry['mode'])
    secure(root)


def test_reader_corpus_guards():
    rows = cases()
    boundary = json.loads((ROOT/'testdata/conformance/reader-boundary-cases.json').read_bytes())['cases']
    assert set(DIAGNOSTICS) == {r['name'] for r in rows+boundary if not r['valid']}
    assert len({r['name'] for r in rows}) == 142
    assert sum(r['valid'] for r in rows) == 25
    assert len({tuple((e['path'],e['type'],e['bytes']) for e in r['entries']) for r in rows}) == 142
    for row in rows:
        assert set(row) == {'name','origin','sourceType','valid','phase','refusal','fullPath','entries'}
        assert type(row['valid']) is bool and row['fullPath'] is True
        assert row['sourceType'] == 'directory'
        assert bool(row['refusal']) != row['valid']
        assert row['entries'] and [e['path'] for e in row['entries']] == sorted(e['path'] for e in row['entries'])
        for entry in row['entries']:
            assert set(entry) == {'path','type','mode','uid','gid','size','digest','linkTarget','bytes'}
            assert entry['uid'] == entry['gid'] == 0 and entry['linkTarget'] == ''
            assert entry['mode'] == (0o755 if entry['type']=='directory' else 0o644)
            if entry['type'] == 'file':
                raw = base64.b64decode(entry['bytes'],validate=True)
                assert len(raw) == entry['size'] and digest_bytes(raw) == entry['digest']
            else:
                assert entry['type'] == 'directory' and entry['bytes'] is None


@pytest.mark.parametrize('row',cases(),ids=lambda row:row['name'])
def test_shared_reader_cases(tmp_path,api,row):
    Package,LoadError = api
    root = tmp_path/'source'
    materialize(root,row)
    if not row['valid']:
        with pytest.raises(LoadError) as error:
            Package.load(root)
        assert_refusal(error,row['name'])
        return
    with Package.load(root) as package:
        identity = next(e['digest'] for e in row['entries'] if e['path']=='agentsuite.json')
        assert package.root_digest == identity
        assert package.artifact_digest is None
        shutil.rmtree(root)
        assert package.validate() == ()
        for agent in package.agents.values():
            body = b''.join(agent.instructions.content.iter_bytes())
            assert digest_bytes(body) == agent.instructions.reference.descriptor.digest


@pytest.mark.parametrize('row',[r for r in cases() if r['valid']],ids=lambda row:row['name'])
def test_shared_reader_oci_positives(tmp_path,api,row):
    Package,_ = api
    root,layout = tmp_path/'source',tmp_path/'layout'
    materialize(root,row)
    packed_fixture(root,layout)
    expected = json.loads((layout/'index.json').read_bytes())['manifests'][0]['digest']
    with Package.load(layout) as package:
        assert package.artifact_digest == expected and package.root_digest != expected
        assert package.root_digest == next(e['digest'] for e in row['entries'] if e['path']=='agentsuite.json')
        shutil.rmtree(root)
        shutil.rmtree(layout)
        assert package.validate() == ()
