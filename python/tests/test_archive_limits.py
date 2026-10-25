"""Content accounting and bounded reads independent of archive byte size."""
import gzip
import hashlib
import io

import pytest

from test_archive_differential import header


def layer(*entries):
    return io.BytesIO(gzip.compress(b"".join(entries) + bytes(1024), mtime=0))


def file(name, data):
    return header(name, size=len(data)) + data + bytes(-len(data) % 512)


def test_archive_limits(monkeypatch):
    from agent_suite import _content as c
    from agent_suite._archive import load_layer
    monkeypatch.setattr(c, "MAX_ENTRIES", 2)
    monkeypatch.setattr(c, "MAX_CONTENT_BYTES", 4)
    monkeypatch.setattr(c, "MAX_RETAINED_BYTES", 3)
    assert len(load_layer(layer(file("a.json", b"{}"), file("b.bin", b"xx"))).entries) == 2
    with pytest.raises(ValueError, match="entry limit"):
        load_layer(layer(file("a", b""), file("b", b""), file("c", b"")))
    with pytest.raises(ValueError, match="regular bytes"):
        load_layer(layer(file("a", b"xxx"), file("b", b"xx")))
    with pytest.raises(ValueError, match="retained metadata"):
        load_layer(layer(file("a.json", b"{}"), file("b.json", b"{}")))
    # A sparse hole counts as logical content before any hole is inflated.
    from test_archive_differential import pax
    sparse = pax([("GNU.sparse.map", "0,0"), ("GNU.sparse.numblocks", "1"), ("GNU.sparse.size", "5")])
    with pytest.raises(ValueError, match="regular bytes"):
        load_layer(layer(sparse + header(size=0)))


def test_archive_streaming_and_retention(monkeypatch):
    from agent_suite import _content as c
    from agent_suite._archive import load_layer
    monkeypatch.setattr(c, "MAX_JSON_BYTES", 4)
    payload = bytes(range(256)) * 4096
    raw = layer(file("payload.bin", payload), file("large.json", b"12345"),
                file("empty.json", b""), file("UPPER.JSON", b"{}"), file("at-limit.json", b"1234")).getvalue()

    class ShortSource(io.BytesIO):
        def read(self, size=-1):
            assert 0 <= size <= 128 << 10, size
            return super().read(min(size, 7))

    source = ShortSource(raw)
    content = load_layer(source)
    assert not source.closed
    assert content.entries["payload.bin"].size == len(payload)
    assert content.entries["payload.bin"].digest == "sha256:" + hashlib.sha256(payload).hexdigest()
    assert content.entries["payload.bin"].data is None
    assert content.entries["large.json"].data is None
    assert content.entries["UPPER.JSON"].data is None
    assert content.data("empty.json") == b""
    assert content.data("at-limit.json") == b"1234"


def test_archive_does_not_extract(tmp_path, monkeypatch):
    from agent_suite._archive import load_layer
    monkeypatch.chdir(tmp_path)
    content = load_layer(layer(file("payload.bin", b"abc")))
    assert set(content.entries) == {"payload.bin"}
    assert list(tmp_path.iterdir()) == []
