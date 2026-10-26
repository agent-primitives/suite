import errno
import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from agent_suite._literals import CHUNK_BYTES, SPOOL_MEMORY_BYTES, LiteralSnapshot
from agent_suite._models import Descriptor, Source
from agent_suite._records import FileRef


def reference(path, data):
    return FileRef(source=Source('agent.json', '/instructions'), path=path,
        descriptor=Descriptor('text/markdown; charset=utf-8', 'sha256:'+hashlib.sha256(data).hexdigest(), len(data)))


def test_small_spool_and_aggregate_rollover(monkeypatch):
    import agent_suite._literals as literals
    created = []
    factory = literals.tempfile.SpooledTemporaryFile
    def tracked(*args, **kwargs):
        file = factory(*args, **kwargs)
        created.append(file)
        return file
    monkeypatch.setattr(literals.tempfile, 'SpooledTemporaryFile', tracked)
    data = b'x'*(SPOOL_MEMORY_BYTES//2+1)
    with LiteralSnapshot() as snapshot:
        first,second = reference('one',data), reference('two',data)
        snapshot.add(first, [data[:CHUNK_BYTES], data[CHUNK_BYTES:]])
        assert len(created) == 1 and not created[0]._rolled
        snapshot.add(second, (data[i:i+CHUNK_BYTES] for i in range(0,len(data),CHUNK_BYTES)))
        assert len(created) == 1 and created[0]._rolled
        snapshot.seal()
        assert b''.join(snapshot.get(first).iter_bytes()) == data
        assert b''.join(snapshot.get(second).iter_bytes()) == data
        file = created[0]._file
        name = file.name
    assert snapshot.closed and file.closed
    if isinstance(name, str):
        assert not Path(name).exists()


def test_reused_metadata_and_empty_literal_need_no_spool(monkeypatch):
    import agent_suite._literals as literals
    def forbidden(*args, **kwargs):
        raise AssertionError('unnecessary spool')
    monkeypatch.setattr(literals.tempfile, 'SpooledTemporaryFile', forbidden)
    body = b'{ "unchanged": true }\n'
    ref = reference('schema.raw',body)
    empty = reference('empty',b'')
    with LiteralSnapshot() as snapshot:
        snapshot.reuse(ref,body)
        snapshot.add(empty, [])
        snapshot.seal()
        assert b''.join(snapshot.get(ref).iter_bytes()) == body
        assert list(snapshot.get(empty).iter_bytes()) == []


def test_large_literal_is_not_a_json_document_limit():
    size = (4<<20)+1
    chunk = b'x'*CHUNK_BYTES
    def chunks():
        for offset in range(0,size,CHUNK_BYTES):
            yield chunk[:min(CHUNK_BYTES,size-offset)]
    expected = hashlib.sha256()
    for block in chunks():
        expected.update(block)
    ref = FileRef(source=Source('agent.json','/instructions'),path='large.md',
        descriptor=Descriptor('text/markdown; charset=utf-8','sha256:'+expected.hexdigest(),size))
    with LiteralSnapshot() as snapshot:
        snapshot.add(ref,chunks())
        snapshot.seal()
        actual = hashlib.sha256()
        total = 0
        for block in snapshot.get(ref).iter_bytes():
            assert 0 < len(block) <= CHUNK_BYTES
            total += len(block)
            actual.update(block)
        assert total == size and actual.digest() == expected.digest()


def test_literal_text_is_incremental_and_bytes_are_authoritative():
    body = b'a'*(CHUNK_BYTES-1)+'€!'.encode()
    ref = reference('utf8.md',body)
    with LiteralSnapshot() as snapshot:
        snapshot.add(ref,[body])
        bad = reference('binary.md',b'\xff\x00x')
        snapshot.add(bad,[b'\xff\x00x'])
        snapshot.seal()
        assert ''.join(snapshot.get(ref).iter_text()) == body.decode()
        with pytest.raises(UnicodeDecodeError):
            list(snapshot.get(bad).iter_text())
        assert ''.join(snapshot.get(bad).iter_text(errors='replace')) == '\ufffd\x00x'
        assert b''.join(snapshot.get(bad).iter_bytes()) == b'\xff\x00x'


def test_literals_interleave_and_read_concurrently():
    first,second = b'a'*(CHUNK_BYTES+19), b'b'*(CHUNK_BYTES*2+7)
    refs = [reference('one',first),reference('two',second)]
    with LiteralSnapshot() as snapshot:
        for ref,body in zip(refs,(first,second)):
            snapshot.add(ref,[body])
        snapshot.seal()
        a,b = (snapshot.get(ref).iter_bytes() for ref in refs)
        assert next(a) == first[:CHUNK_BYTES]
        assert next(b) == second[:CHUNK_BYTES]
        assert b''.join(a) == first[CHUNK_BYTES:]
        assert b''.join(b) == second[CHUNK_BYTES:]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda i:b''.join(snapshot.get(refs[i%2]).iter_bytes()), range(8)))
        assert results == [first,second]*4


def test_literal_close_and_seal_are_explicit():
    body = b'a'*(CHUNK_BYTES+1)
    ref = reference('file',body)
    snapshot = LiteralSnapshot()
    snapshot.add(ref,[body])
    with pytest.raises(ValueError, match='sealed'):
        snapshot.get(ref)
    snapshot.seal()
    with pytest.raises(ValueError, match='sealed'):
        snapshot.add(reference('another',b''), [])
    iterator = snapshot.get(ref).iter_bytes()
    assert next(iterator) == body[:CHUNK_BYTES]
    snapshot.close()
    snapshot.close()
    with pytest.raises(ValueError, match='closed'):
        next(iterator)
    with pytest.raises(ValueError, match='closed'):
        snapshot.get(ref)
    with pytest.raises(ValueError, match='closed'):
        snapshot.__enter__()


@pytest.mark.parametrize('failure', ['size','digest','cancel'])
def test_failed_literal_capture_closes_snapshot(failure):
    ref = reference('file',b'expected')
    def chunks():
        yield b'wrong' if failure == 'size' else b'12345678'
        if failure == 'cancel':
            raise KeyboardInterrupt()
    snapshot = LiteralSnapshot()
    with pytest.raises(KeyboardInterrupt if failure == 'cancel' else ValueError):
        snapshot.add(ref,chunks())
    assert snapshot.closed


def test_get_checks_each_reference_without_changing_source():
    body = b'body'
    original = reference('shared',body)
    with LiteralSnapshot() as snapshot:
        snapshot.add(original,[body])
        snapshot.seal()
        later = replace(original,source=Source('provider.json','/tools/1/inputSchema'))
        assert snapshot.get(later).reference.source == later.source
        bad = replace(later,descriptor=replace(later.descriptor,digest='sha256:'+'0'*64))
        with pytest.raises(ValueError, match='pin'):
            snapshot.get(bad)


def test_short_spool_writes_are_completed_and_disk_full_propagates(monkeypatch):
    import agent_suite._literals as literals
    factory = literals.tempfile.SpooledTemporaryFile
    created = []
    class Short:
        def __init__(self, **kwargs):
            self.file = factory(**kwargs)
            self.fail = False
            created.append(self)
        def write(self, data):
            if self.fail:
                raise OSError(errno.ENOSPC,'disk full')
            return self.file.write(data[:7])
        def __getattr__(self, name):
            return getattr(self.file,name)
    monkeypatch.setattr(literals.tempfile,'SpooledTemporaryFile',Short)
    body = b'full body'*20
    ref = reference('file',body)
    with LiteralSnapshot() as snapshot:
        snapshot.add(ref,[body])
        snapshot.seal()
        assert b''.join(snapshot.get(ref).iter_bytes()) == body
    snapshot = LiteralSnapshot()
    def chunks():
        yield b'a'
        created[-1].fail = True
        yield b'b'
    with pytest.raises(OSError) as error:
        snapshot.add(reference('fail',b'ab'),chunks())
    assert error.value.errno == errno.ENOSPC and snapshot.closed and created[-1].closed
