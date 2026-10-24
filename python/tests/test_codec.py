"""The Go-owned corpus is mandatory; never replace it with Python translations."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORPUS = Path(os.environ.get("AGENT_SUITE_CONFORMANCE_ROOT", ROOT / "testdata/conformance"))


def cases(filename, minimum):
    data = (CORPUS / filename).read_bytes()
    assert data.endswith(b"\n"), "corpus must end with LF"
    result = [json.loads(line) for line in data.splitlines()]
    assert len(result) >= minimum, "truncated corpus"
    assert all(c.get("name") for c in result)
    assert len({c["name"] for c in result}) == len(result), "duplicate case names"
    return result


def test_internal_modules_exist():
    assert importlib.util.find_spec("agent_suite") is not None, "foundation package missing"


def test_shared_json_conformance():
    from agent_suite._json import canonical_bytes, decode, digest_bytes
    from agent_suite._models import Descriptor, Platform

    population = cases("json-cases.jsonl", 31)
    assert {c["valid"] for c in population} == {True, False}
    counts = {"json": 0, "descriptor": 0, "platform": 0}
    for case in population:
        assert case["target"] in counts, "unknown corpus target"
        counts[case["target"]] += 1
        assert ("input" in case) != ("inputHex" in case)
        assert all((key in case) == case["valid"] for key in ("canonical", "digest", "size"))
        data = case["input"].encode() if "input" in case else bytes.fromhex(case["inputHex"])
        try:
            value = decode(data)
            if case["target"] == "descriptor":
                Descriptor.from_value(value)
            elif case["target"] == "platform":
                Platform.from_value(value)
            encoded = canonical_bytes(value)
        except ValueError:
            assert not case["valid"], case["name"]
        else:
            assert case["valid"], case["name"]
            assert encoded == case["canonical"].encode(), case["name"]
            assert len(encoded) == case["size"]
            assert digest_bytes(encoded) == case["digest"]
    assert all(counts.values())


def test_shared_variant_conformance():
    from agent_suite._json import canonical_bytes, decode, digest_bytes, variant_bytes

    for case in cases("variant-cases.jsonl", 2):
        provider = decode(case["input"].encode())
        before = canonical_bytes(provider)
        encoded = variant_bytes(provider["variants"][0])
        assert encoded == case["canonical"].encode()
        assert digest_bytes(encoded) == case["digest"]
        assert canonical_bytes(provider) == before


@pytest.mark.parametrize("lexeme,canonical", [
    ("-0", "0"), ("-0.0", "0"), ("1e2", "100"), ("1.0", "1"),
    ("9007199254740992", "9007199254740992"),
    ("9007199254740994", "9007199254740994"),
    ("9007199254740993.0", "9007199254740992"),
    ("1000000000000000000001", "1e+21"),
    ("333333333.33333329", "333333333.3333333"),
])
def test_go_number_lexeme_semantics(lexeme, canonical):
    from agent_suite._json import canonical_bytes, decode
    assert canonical_bytes(decode(lexeme.encode())) == canonical.encode()


@pytest.mark.parametrize("data", [
    b"", b"9007199254740993", b"9223372036854775807", b"1e400", b"NaN", b"Infinity",
    b'"\\ud800"', b'"\\udc00"', b'{"a":1,"\\u0061":2}', b"\xef\xbb\xbf{}",
    b"\xff", b"{} {}", b"{}x", b"[" * 101 + b"0" + b"]" * 101,
    b" " * (4 * 1024 * 1024) + b"0",
], ids=[
    "empty", "lossy-integer", "int64-rounding", "overflow", "nan", "infinity",
    "high-surrogate", "low-surrogate", "duplicate-key", "bom", "invalid-utf8",
    "trailing-value", "trailing-junk", "excessive-depth", "oversized-document",
])
def test_strict_refusals(data):
    from agent_suite._json import decode
    with pytest.raises(ValueError):
        decode(data)


def test_utf16_order_and_literal_digest():
    from agent_suite._json import canonical_bytes, decode, digest_bytes
    data = '{"\ue000":0,"😀":1,"a":"<>&"}'.encode()
    assert canonical_bytes(decode(data)) == '{"a":"<>&","😀":1,"\ue000":0}'.encode()
    assert digest_bytes(b"literal\n") == "sha256:" + hashlib.sha256(b"literal\n").hexdigest()
    assert digest_bytes(b"literal\n") != digest_bytes(b"literal")


def test_member_and_byte_boundaries():
    from agent_suite._json import decode
    assert decode(b"0" + b" " * (4 * 1024 * 1024 - 1)) == 0
    assert decode(json.dumps(dict.fromkeys(map(str, range(1024)), 0)).encode())
    with pytest.raises(ValueError, match="member"):
        decode(json.dumps(dict.fromkeys(map(str, range(1025)), 0)).encode())
    # Array entries are not object members. Exactly 100,000 members is legal.
    data = [{str(i): 0 for i in range(1000)} for _ in range(100)]
    assert len(decode(json.dumps(data).encode())) == 100
    data.append({"extra": 0})
    with pytest.raises(ValueError, match="member"):
        decode(json.dumps(data).encode())


def test_variant_blanks_only_own_pin():
    from agent_suite._json import canonical_bytes, decode, variant_bytes
    value = decode(b'{"variantDigest":null,"arguments":null,"dependencies":[{"variantDigest":"keep"}]}')
    assert variant_bytes(value) == b'{"arguments":null,"dependencies":[{"variantDigest":"keep"}],"variantDigest":""}'
    assert b'"variantDigest":null' in canonical_bytes(value)
    with pytest.raises(ValueError, match="variantDigest"):
        variant_bytes({})


@pytest.mark.parametrize("size", ["2.0", "2e0", "true", "9223372036854775808"])
def test_descriptor_integer_lexeme(size):
    from agent_suite._json import decode
    from agent_suite._models import Descriptor
    with pytest.raises(ValueError, match="size"):
        Descriptor.from_value(decode(('{"mediaType":"x","digest":"x","size":' + size + '}').encode()))


def test_go_numeric_differential():
    import subprocess

    from agent_suite._json import canonical_bytes, decode
    from agent_suite._models import Descriptor

    lexemes = ["0", "-0", "-0.0", "1.0", "1e2", "9007199254740992",
               "9007199254740993", "9007199254740994", "9007199254740993.0",
               "9223372036854775807", "-9223372036854775808",
               "9223372036854775808", "1000000000000000000001", "1e400",
               "333333333.33333329", "1e-7", "1e-6", "1e20", "1e21"]
    requests = [{"Input": number, "Target": "json"} for number in lexemes]
    requests += [{"Input": '{"mediaType":"x","digest":"x","size":' + number + '}',
                  "Target": "descriptor"} for number in lexemes]
    oracle = subprocess.run(
        ["go", "run", "./python/tests/testdata/oracle.go"], cwd=ROOT,
        input="".join(json.dumps(item) + "\n" for item in requests),
        text=True, capture_output=True, check=True,
    )
    responses = [json.loads(line) for line in oracle.stdout.splitlines()]
    assert len(responses) == len(requests)
    for request, expected in zip(requests, responses):
        try:
            value = decode(request["Input"].encode())
            if request["Target"] == "descriptor":
                Descriptor.from_value(value)
            canonical = canonical_bytes(value).decode()
        except ValueError:
            assert not expected["Valid"], request
        else:
            assert expected["Valid"], request
            assert canonical == expected["Canonical"], request


def test_raw_document_keeps_presence_bytes_and_source():
    from agent_suite._models import Document, Source
    raw = b'{ "arguments":[], "other":null, "relocatable":false }'
    document = Document.from_bytes(raw, Source("provider.json", "/variants/0"))
    assert document.data == raw
    assert "missing" not in document.value
    assert document.value["other"] is None
    assert document.value["relocatable"] is False
    assert document.value["arguments"] == []
    assert document.source == Source("provider.json", "/variants/0")
    # No mutable alias escapes the record.
    tree = document.value
    tree["arguments"].append(1)
    assert document.value["arguments"] == []
