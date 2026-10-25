"""Regression for legal PAX inputs with disproportionate parsing work."""
from agent_suite._tar import _pax


def test_pax_linear_work():
    class CountedBytes(bytes):
        copied = 0

        def __getitem__(self, key):
            result = super().__getitem__(key)
            if isinstance(result, bytes):
                type(self).copied += len(result)
                return type(self)(result)
            return result

    # Count real sliced bytes, not wall-clock time: no host-speed-dependent gate.
    raw = CountedBytes(b"6 x=y\n" * 2000)
    assert _pax(raw) == {"x": "y"}
    assert CountedBytes.copied <= 3 * len(raw)


def test_sparse_map_linear_work(monkeypatch):
    import gzip
    import io
    from agent_suite._archive import load_layer
    from agent_suite._tar import TarReader
    from test_archive_differential import header, pax

    class CountedBytes(bytes):
        scanned = 0

        def __add__(self, other):
            return type(self)(bytes(self) + other)

        def __radd__(self, other):
            return type(self)(other + bytes(self))

        def split(self, *args):
            type(self).scanned += len(self)
            return [type(self)(part) for part in super().split(*args)]

    original = TarReader._physical

    def counted_read(reader, size):
        return CountedBytes(original(reader, size))

    monkeypatch.setattr(TarReader, "_physical", counted_read)
    body = b"0" * ((1 << 17) - 1) + b"\n"
    values = [("GNU.sparse.major", "1"), ("GNU.sparse.minor", "0"),
              ("GNU.sparse.realsize", "0")]
    raw = pax(values) + header(size=len(body)) + body + bytes(1024)
    content = load_layer(io.BytesIO(gzip.compress(raw, mtime=0)))
    assert content.data("file.json") == b""
    assert CountedBytes.scanned <= 2 * len(body)
