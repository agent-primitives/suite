"""Private raw-layer compatibility; loading is not package validation."""
import base64
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def archive_cases(corpus):
    cases = corpus["cases"]
    names = [case["name"] for case in cases]
    assert len(names) >= 94 and len(set(names)) == len(names) and all(names)
    assert all(type(case["valid"]) is bool for case in cases)
    assert sum(case["valid"] for case in cases) >= 40
    assert sum(not case["valid"] for case in cases) >= 54
    return cases


def test_archive_corpus_guards():
    corpus = json.loads((ROOT / "testdata/conformance/archive-cases.json").read_bytes())
    archive_cases(corpus)
    for mutation in [[], corpus["cases"][:-1], [corpus["cases"][0]] * 94]:
        with pytest.raises(AssertionError):
            archive_cases({"cases": mutation})
    for key, value in [("name", ""), ("valid", None), ("valid", "false")]:
        changed = [dict(case) for case in corpus["cases"]]
        changed[0][key] = value
        with pytest.raises(AssertionError):
            archive_cases({"cases": changed})


def test_shared_archive_cases():
    import importlib.util
    assert importlib.util.find_spec("agent_suite._archive") is not None, "private layer loader missing"
    from agent_suite._archive import load_layer
    corpus = json.loads((ROOT / "testdata/conformance/archive-cases.json").read_bytes())
    for case in archive_cases(corpus):
        raw = base64.b64decode(case["gzip"], validate=True)
        try:
            content = load_layer(io.BytesIO(raw))
        except ValueError:
            assert not case["valid"], case["name"]
            continue
        assert case["valid"], case["name"]
        assert content.source_type == ""
        entries = [dict(Path=e.path, Type=e.kind, Mode=e.mode, UID=e.uid, GID=e.gid,
                        Size=e.size, Digest=e.digest, LinkTarget=e.link_target,
                        Data=None if e.data is None else base64.b64encode(e.data).decode())
                   for e in sorted(content.entries.values(), key=lambda e: e.path)]
        assert entries == case["entries"], case["name"]
