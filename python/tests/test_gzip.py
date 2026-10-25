"""Independent gzip framing vectors; no high-level gzip reader or writer."""
import io
import random
import struct
import tracemalloc
import zlib

import pytest


def member(data=b"", *, mtime=0, flags=0, extra=None, name=None, comment=None,
           header_crc=False):
    flags |= (4 if extra is not None else 0) | (8 if name is not None else 0)
    flags |= (16 if comment is not None else 0) | (2 if header_crc else 0)
    header = b"\x1f\x8b\x08" + bytes([flags]) + struct.pack("<I", mtime) + b"\x00\xff"
    if extra is not None:
        header += struct.pack("<H", len(extra)) + extra
    for value in (name, comment):
        if value is not None:
            header += value + b"\x00"
    if header_crc:
        header += struct.pack("<H", zlib.crc32(header) & 0xffff)
    compressor = zlib.compressobj(wbits=-15)
    return header + compressor.compress(data) + compressor.flush() + struct.pack(
        "<II", zlib.crc32(data), len(data) & 0xffffffff
    )


class ShortSource(io.BytesIO):
    def __init__(self, data, chunk=1):
        super().__init__(data)
        self.chunk = chunk
        self.calls = 0

    def read(self, size=-1):
        assert 0 < size <= 65536, "compressed input reads must be bounded"
        self.calls += 1
        return super().read(min(size, self.chunk))

    def seek(self, *args):
        raise AssertionError("caller stream must not be sought")


def reader(raw, source=None):
    from agent_suite._gzip import GzipReader
    return GzipReader(io.BytesIO(raw) if source is None else source)


def drain(stream, size=17):
    chunks = []
    while True:
        chunk = stream.read(size)
        assert len(chunk) <= size
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def test_empty_member_and_zero_reads_do_not_close_or_seek_source():
    source = ShortSource(member())
    stream = reader(b"", source)
    assert stream.read(0) == b""
    assert source.calls == 0
    assert drain(stream) == b""
    assert stream.read(1) == b""
    assert not source.closed


@pytest.mark.parametrize("size", [1, 7, 65536])
def test_one_byte_source_short_reads(size):
    data = bytes(range(256)) * 20
    source = ShortSource(member(data))
    assert drain(reader(b"", source), size) == data
    assert not source.closed


@pytest.mark.parametrize("kwargs", [
    {"extra": b"\x00\xff" * 32767 + b"x"},
    {"name": b"\xff" * 511},
    {"comment": b"c" * 511},
    {"extra": b"", "name": b"", "comment": b"", "header_crc": True},
    {"extra": b"ab", "name": b"\xffname", "comment": b"comment", "header_crc": True},
    {"flags": 0xe1},
])
def test_go_compatible_optional_headers(kwargs):
    assert drain(reader(member(b"payload", **kwargs))) == b"payload"


@pytest.mark.parametrize("field", ["name", "comment"])
def test_optional_string_limit_includes_nul(field):
    with pytest.raises(ValueError):
        drain(reader(member(b"payload", **{field: b"x" * 512})))


def test_initial_mtime_only_is_restricted():
    with pytest.raises(ValueError, match="[Mm][Tt][Ii][Mm][Ee]|modification"):
        drain(reader(member(b"a", mtime=1)))
    raw = member() + member(b"a", mtime=0xffffffff) + member(mtime=1) + member(b"b")
    assert drain(reader(raw), 1) == b"ab"


def test_concatenated_empty_members_never_signal_early_eof():
    raw = member() * 3 + member(b"a") + member() * 2 + member(b"b") + member() * 3
    stream = reader(raw)
    assert stream.read(1) == b"a"
    assert stream.read(1) == b"b"
    assert stream.read(1) == b""


@pytest.mark.parametrize("suffix", [b"\x00", b"\x00" * 64, b"garbage", b"\x1f\x8b"])
def test_nonmember_tail_cannot_hide_after_last_payload(suffix):
    stream = reader(member(b"a") + member() + suffix)
    assert stream.read(1) == b"a"
    with pytest.raises(ValueError):
        stream.read(1)


@pytest.mark.parametrize("offset", [-8, -4])
@pytest.mark.parametrize("prefix", [b"", member(b"first")])
def test_every_member_crc_and_size_are_verified(offset, prefix):
    raw = bytearray(member(b"payload"))
    raw[offset] ^= 1
    with pytest.raises(ValueError, match="checksum|CRC|size"):
        drain(reader(prefix + raw), 1)


def test_all_header_deflate_and_trailer_truncations_fail():
    raw = member(b"payload", extra=b"extra", name=b"name", comment=b"comment", header_crc=True)
    for end in range(len(raw)):
        with pytest.raises(ValueError):
            drain(reader(raw[:end]), 1)


def test_corrupt_header_crc_is_rejected():
    raw = bytearray(member(b"data", name=b"name", header_crc=True))
    raw[15] ^= 1
    with pytest.raises(ValueError):
        drain(reader(raw))


@pytest.mark.parametrize("header", [b"\x00\x8b\x08", b"\x1f\x00\x08", b"\x1f\x8b\x00"])
def test_magic_and_compression_method_are_checked(header):
    with pytest.raises(ValueError):
        drain(reader(header + member()[3:]))


def test_deflate_errors_have_gzip_context():
    raw = member()[:10] + b"\x07" + b"\x00" * 8
    with pytest.raises(ValueError, match="gzip|deflate") as error:
        drain(reader(raw))
    assert isinstance(error.value.__cause__, zlib.error)


def test_compressed_chunk_bound_and_buffered_output_survive_tiny_reads():
    data = random.Random(731).randbytes(180000) + b"x" * 300000
    source = ShortSource(member(data), chunk=65536)
    assert drain(reader(b"", source), 3) == data


def test_high_expansion_output_is_bounded_without_eager_allocation():
    # Construct before tracing: retaining or inflating the whole 16 MiB would fail.
    raw = member(b"x" * (16 << 20))
    tracemalloc.start()
    try:
        stream = reader(raw)
        total = 0
        while chunk := stream.read(4096):
            assert 0 < len(chunk) <= 4096
            assert chunk == b"x" * len(chunk)
            total += len(chunk)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert total == 16 << 20
    assert peak < 2 << 20
