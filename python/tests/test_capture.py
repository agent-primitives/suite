import base64
import json
import os
import shutil
from dataclasses import replace

import pytest

from agent_suite._capture import capture_directory, capture_oci_layout
from agent_suite._directory import load_directory
from agent_suite._documents import read_documents
from agent_suite._json import canonical_bytes, digest_bytes
from agent_suite._oci import load_oci_layout
from agent_suite._record_decode import DocumentError
from agent_suite._schema import Bundle
from test_documents import ROOT
from test_oci import materialize


@pytest.fixture
def bundle():
    return Bundle.from_bytes({p.name:p.read_bytes() for p in (ROOT/'schema').glob('*.json')})


def secure(root):
    if os.name == 'nt':
        from _directory_windows_fixture import secure_fixture
        secure_fixture(root)


def extracted(tmp_path, name='minimal'):
    cases = json.loads((ROOT/'testdata/conformance/graph-cases.json').read_bytes())['cases']
    case = next(c for c in cases if c['name'] == name)
    root = tmp_path/'source'
    root.mkdir()
    for entry in case['entries']:
        path = root/entry['path']
        if entry['type'] == 'directory':
            path.mkdir(parents=True,exist_ok=True)
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(base64.b64decode(entry['bytes']))
    return root, {e['path']:base64.b64decode(e['bytes']) for e in case['entries'] if e['bytes'] is not None}


def references(documents):
    result = [a.record.instructions for a in documents.agents]
    for provider in documents.providers:
        for tool in provider.record.tools:
            result.append(tool.input_schema)
            if tool.output_schema is not None:
                result.append(tool.output_schema)
    return result


def literal_fixture(tmp_path,row):
    root,_ = extracted(tmp_path)
    raw = lambda key:base64.b64decode(row[key],validate=True)
    body = raw('prefix')+raw('block')*row['repeat']+raw('suffix')
    assert len(body) == row['size'] and digest_bytes(body) == row['digest']
    target = root/row['path']
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(body)
    descriptor = dict(mediaType='text/markdown; charset=utf-8',size=row['size'],digest=row['digest'])
    ref = dict(path=row['path'],descriptor=descriptor)
    suite = json.loads((root/'agentsuite.json').read_bytes())
    if row['target'] == 'instructions':
        path = root/'agents/writer.json'
        agent = json.loads(path.read_bytes())
        agent['instructions'] = ref
        data = canonical_bytes(agent)
        path.write_bytes(data)
        suite['agents'][0]['descriptor'].update(size=len(data),digest=digest_bytes(data))
    else:
        assert row['target'] in ('inputSchema','outputSchema')
        (root/'schemas').mkdir(exist_ok=True)
        for path in (ROOT/'testdata/remote-mcp/schemas').iterdir():
            shutil.copyfile(path,root/'schemas'/path.name)
        provider = json.loads((ROOT/'testdata/remote-mcp/tool-provider.json').read_bytes())
        descriptor['mediaType'] = 'application/schema+json'
        provider['tools'][0][row['target']] = ref
        provider_path = 'tool-providers/search/1.0.0/tool-provider.json'
        (root/provider_path).parent.mkdir(parents=True,exist_ok=True)
        data = canonical_bytes(provider)
        (root/provider_path).write_bytes(data)
        catalog_path = root/'tool-providers/catalog.json'
        catalog = json.loads(catalog_path.read_bytes())
        catalog['toolProviders'].append(dict(id='search',version='1.0.0',path=provider_path,
            descriptor=dict(mediaType=provider['mediaType'],size=len(data),digest=digest_bytes(data))))
        data = canonical_bytes(catalog)
        catalog_path.write_bytes(data)
        suite['toolProviderCatalog']['descriptor'].update(size=len(data),digest=digest_bytes(data))
    (root/'agentsuite.json').write_bytes(canonical_bytes(suite))
    assert digest_bytes((root/'agentsuite.json').read_bytes()) == row['rootDigest']
    return root,body


def packed_fixture(root,layout):
    import gzip
    import io
    import tarfile
    materialize(layout,{'layout':'minimal-0644'})
    buffer = io.BytesIO()
    payload_end = 0
    with tarfile.open(fileobj=buffer,mode='w',format=tarfile.USTAR_FORMAT) as archive:
        for path in sorted(root.rglob('*')):
            entry = tarfile.TarInfo(path.relative_to(root).as_posix())
            entry.mode = 0o755 if path.is_dir() else 0o644
            if path.is_dir():
                entry.type = tarfile.DIRTYPE
                archive.addfile(entry)
            else:
                body = path.read_bytes()
                entry.size = len(body)
                archive.addfile(entry,io.BytesIO(body))
            payload_end += 512 + (entry.size+511)//512*512
    # Omit tarfile's extra record padding after the required two end blocks.
    layer = gzip.compress(buffer.getvalue()[:payload_end+1024],mtime=0)
    blobs = layout/'blobs/sha256'
    index = json.loads((layout/'index.json').read_bytes())
    selected = index['manifests'][0]
    manifest = json.loads((blobs/selected['digest'][7:]).read_bytes())
    manifest['layers'][0].update(size=len(layer),digest=digest_bytes(layer))
    (blobs/digest_bytes(layer)[7:]).write_bytes(layer)
    data = canonical_bytes(manifest)
    (blobs/digest_bytes(data)[7:]).write_bytes(data)
    selected.update(size=len(data),digest=digest_bytes(data))
    (layout/'index.json').write_bytes(canonical_bytes(index))


def test_shared_literal_capture_cases(tmp_path,bundle):
    rows = json.loads((ROOT/'testdata/conformance/literal-cases.json').read_bytes())['cases']
    assert len(rows) == len({r['name'] for r in rows}) == 6
    for row in rows:
        work = tmp_path/row['name']
        work.mkdir()
        root,expected = literal_fixture(work,row)
        layout = work/'layout'
        packed_fixture(root,layout)
        secure(root)
        for path,loader,capture in [(root,load_directory,capture_directory),(layout,load_oci_layout,capture_oci_layout)]:
            content = loader(path)
            documents = read_documents(content,bundle)
            assert digest_bytes(canonical_bytes(documents.suite.document.value)) == row['rootDigest']
            ref = next(r for r in references(documents) if r.path == row['path'])
            if row['size'] > 4<<20 or not row['path'].endswith('.json'):
                assert content.entries[ref.path].data is None
            with capture(path,content,documents) as snapshot:
                shutil.rmtree(path)
                assert b''.join(snapshot.get(ref).iter_bytes()) == expected
            assert snapshot.closed


@pytest.mark.parametrize('name', ['minimal','remote','bundled','runtime-two-profiles'])
def test_captured_go_fixture_literals_outlive_directory(tmp_path,bundle,name):
    root,bodies = extracted(tmp_path,name)
    secure(root)
    content = load_directory(root)
    documents = read_documents(content,bundle)
    refs = references(documents)
    with capture_directory(root,content,documents) as snapshot:
        shutil.rmtree(root)
        assert not root.exists()
        for ref in refs:
            assert b''.join(snapshot.get(ref).iter_bytes()) == bodies[ref.path]
    assert snapshot.closed


def test_large_arbitrary_instruction_is_captured_without_new_limit(tmp_path,bundle):
    root,_ = extracted(tmp_path)
    path = 'payload/instruction.data'
    body = b'x'*((4<<20)+1)
    (root/'payload').mkdir()
    (root/path).write_bytes(body)
    agent_path = root/'agents/writer.json'
    agent = json.loads(agent_path.read_bytes())
    agent['instructions']['path'] = path
    agent['instructions']['descriptor'].update(size=len(body),digest=digest_bytes(body))
    agent_raw = canonical_bytes(agent)
    agent_path.write_bytes(agent_raw)
    suite = json.loads((root/'agentsuite.json').read_bytes())
    suite['agents'][0]['descriptor'].update(size=len(agent_raw),digest=digest_bytes(agent_raw))
    (root/'agentsuite.json').write_bytes(canonical_bytes(suite))
    secure(root)
    content = load_directory(root)
    assert content.entries[path].data is None
    documents = read_documents(content,bundle)
    with capture_directory(root,content,documents) as snapshot:
        shutil.rmtree(root)
        actual = b''.join(snapshot.get(documents.agents[0].record.instructions).iter_bytes())
        assert actual == body


def test_captured_literals_outlive_oci_layout(tmp_path,bundle):
    corpus = json.loads((ROOT/'testdata/conformance/oci-cases.json').read_bytes())
    root = tmp_path/'layout'
    materialize(root,next(c for c in corpus['cases'] if c['name']=='stored-minimal-0644'))
    content = load_oci_layout(root)
    documents = read_documents(content,bundle)
    import tarfile
    index = json.loads((root/'index.json').read_bytes())
    manifest = json.loads((root/'blobs/sha256'/index['manifests'][0]['digest'][7:]).read_bytes())
    layer = root/'blobs/sha256'/manifest['layers'][0]['digest'][7:]
    with tarfile.open(layer, 'r:gz') as archive:
        file = archive.extractfile(documents.agents[0].record.instructions.path)
        assert file is not None
        expected = file.read()
    with capture_oci_layout(root,content,documents) as snapshot:
        shutil.rmtree(root)
        assert b''.join(snapshot.get(documents.agents[0].record.instructions).iter_bytes()) == expected


@pytest.mark.parametrize('mutation', ['changed','short','link','parent-link'])
def test_directory_capture_refuses_changed_source_and_links(tmp_path,bundle,mutation):
    root,_ = extracted(tmp_path)
    secure(root)
    content = load_directory(root)
    documents = read_documents(content,bundle)
    target = root/documents.agents[0].record.instructions.path
    if mutation == 'changed':
        target.write_bytes(b'x'*target.stat().st_size)
    elif mutation == 'short':
        target.write_bytes(b'x')
    elif mutation == 'link':
        target.unlink()
        target.symlink_to(root/'agents/writer.json')
    else:
        original = root/'instructions'
        moved = root/'other'
        original.rename(moved)
        original.symlink_to(moved,target_is_directory=True)
    expected = {
        'changed': (ValueError,'literal pin mismatch'),
        'short': (ValueError,'literal size changed'),
        'link': ((ValueError,OSError),None),
        'parent-link': ((ValueError,OSError),None),
    }
    errors,message = expected[mutation]
    with pytest.raises(errors,match=message):
        capture_directory(root,content,documents)


def test_directory_capture_checks_opened_kind_not_only_inode(tmp_path,bundle,monkeypatch):
    import stat
    import agent_suite._capture as capture
    root,_ = extracted(tmp_path)
    secure(root)
    content = load_directory(root)
    documents = read_documents(content,bundle)
    check = capture.Native.check
    def changed_kind(self,fd,root=False):
        info = check(self,fd,root=root)
        if stat.S_ISREG(info.st_mode):
            values = list(info)
            values[0] = stat.S_IFDIR | stat.S_IMODE(info.st_mode)
            return os.stat_result(values)
        return info
    monkeypatch.setattr(capture.Native,'check',changed_kind)
    with pytest.raises((ValueError,OSError),match='changed|type'):
        capture_directory(root,content,documents)


def test_retained_tool_schema_is_original_not_reread(tmp_path,bundle):
    root,_ = extracted(tmp_path,'remote')
    secure(root)
    content = load_directory(root)
    documents = read_documents(content,bundle)
    ref = documents.providers[0].record.tools[0].input_schema
    expected = content.entries[ref.path].data
    assert expected is not None
    (root/ref.path).write_bytes(b'changed after verified scan')
    with capture_directory(root,content,documents) as snapshot:
        shutil.rmtree(root)
        assert b''.join(snapshot.get(ref).iter_bytes()) == expected


def test_oci_capture_requires_original_artifact_identity(tmp_path,bundle):
    corpus = json.loads((ROOT/'testdata/conformance/oci-cases.json').read_bytes())
    root = tmp_path/'layout'
    materialize(root,next(c for c in corpus['cases'] if c['name']=='stored-minimal-0644'))
    content = load_oci_layout(root)
    documents = read_documents(content,bundle)
    content.artifact_digest = 'sha256:'+'0'*64
    with pytest.raises(ValueError,match='artifact'):
        capture_oci_layout(root,content,documents)


@pytest.mark.parametrize('cancel', [False,True])
def test_capture_failure_closes_native_source_handles(tmp_path,bundle,monkeypatch,cancel):
    import agent_suite._capture as capture
    root,_ = extracted(tmp_path)
    secure(root)
    content = load_directory(root)
    documents = read_documents(content,bundle)
    opened,snapshots = [],[]
    native,snapshot_type = capture.Native,capture.LiteralSnapshot
    class Tracked(native):
        def open_root(self,path):
            fd = super().open_root(path)
            opened.append(fd)
            return fd
        def open_child(self,parent,name,directory):
            fd = super().open_child(parent,name,directory)
            opened.append(fd)
            return fd
    class Failing(snapshot_type):
        def __init__(self):
            super().__init__()
            snapshots.append(self)
        def add(self,ref,chunks):
            assert next(iter(chunks))
            raise KeyboardInterrupt() if cancel else OSError('disk full')
    monkeypatch.setattr(capture,'Native',Tracked)
    monkeypatch.setattr(capture,'LiteralSnapshot',Failing)
    with pytest.raises(KeyboardInterrupt if cancel else OSError):
        capture.capture_directory(root,content,documents)
    assert snapshots[0].closed and opened
    for fd in opened:
        with pytest.raises(OSError):
            os.fstat(fd)
    shutil.rmtree(root)


def test_oci_snapshot_disk_full_is_io_failure_and_cleans_up(tmp_path,bundle,monkeypatch):
    import errno
    import agent_suite._capture as capture
    root = tmp_path/'layout'
    materialize(root,{'layout':'minimal-0644'})
    content = load_oci_layout(root)
    documents = read_documents(content,bundle)
    snapshots = []
    class Full(capture.LiteralSnapshot):
        def __init__(self):
            super().__init__()
            snapshots.append(self)
        def add(self,ref,chunks):
            raise OSError(errno.ENOSPC,'disk full')
    monkeypatch.setattr(capture,'LiteralSnapshot',Full)
    with pytest.raises(OSError) as error:
        capture.capture_oci_layout(root,content,documents)
    assert error.value.errno == errno.ENOSPC and snapshots[0].closed
    shutil.rmtree(root)


def test_capture_rechecks_later_reference_before_reuse(tmp_path,bundle):
    root,_ = extracted(tmp_path)
    secure(root)
    content = load_directory(root)
    documents = read_documents(content,bundle)
    agent = documents.agents[0]
    stale = replace(agent.record.instructions,
        descriptor=replace(agent.record.instructions.descriptor,size=1))
    documents = replace(documents,agents=documents.agents+(replace(agent,record=replace(agent.record,instructions=stale)),))
    with pytest.raises(DocumentError) as error:
        capture_directory(root,content,documents)
    assert [(d.code,d.source.file,d.source.pointer) for d in error.value.diagnostics] == [
        ('pin.size',stale.source.file,stale.source.pointer+'/descriptor')]
