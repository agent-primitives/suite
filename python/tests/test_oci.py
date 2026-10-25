"""Shared literal envelope mutations; no package graph validation."""
import base64
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def oci_cases(corpus):
    cases = corpus['cases']
    names = [case['name'] for case in cases]
    assert len(set(names)) == len(names) and all(names)
    assert all(type(case['valid']) is bool for case in cases)
    assert sum(case['valid'] for case in cases) >= 29
    assert sum(not case['valid'] for case in cases) >= 83
    return cases


def materialize(root, case):
    if case.get('layout'):
        shutil.copytree(ROOT / 'testdata/conformance/oci' / case['layout'], root, dirs_exist_ok=True)
    for path, data in case.get('files', {}).items():
        target = root / path
        if data is None:
            target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(base64.b64decode(data, validate=True))


def snapshot(content):
    return [dict(Path=e.path, Type=e.kind, Mode=e.mode, UID=e.uid, GID=e.gid,
                 Size=e.size, Digest=e.digest, LinkTarget=e.link_target,
                 Data=None if e.data is None else base64.b64encode(e.data).decode())
            for e in sorted(content.entries.values(), key=lambda e: e.path)]


def test_shared_oci_cases(tmp_path):
    assert importlib.util.find_spec('agent_suite._oci') is not None, 'private OCI loader missing'
    from agent_suite._oci import load_oci_layout
    archive = json.loads((ROOT / 'testdata/conformance/archive-cases.json').read_bytes())
    goldens = {c['name']: c['entries'] for c in archive['cases'] if c['valid']}
    corpus = json.loads((ROOT / 'testdata/conformance/oci-cases.json').read_bytes())
    for case in oci_cases(corpus):
        root = tmp_path / case['name']
        materialize(root, case)
        try:
            content = load_oci_layout(root)
        except (ValueError, OSError):
            assert not case['valid'], case['name']
            continue
        assert case['valid'], case['name']
        assert content.source_type == 'oci-layout'
        assert content.artifact_digest == case['artifactDigest'], case['name']
        assert snapshot(content) == goldens[case['archiveCase']], case['name']


def test_oci_corpus_guards():
    corpus = json.loads((ROOT / 'testdata/conformance/oci-cases.json').read_bytes())
    oci_cases(corpus)
    for cases in [[], corpus['cases'][:1], corpus['cases'][:-1], [corpus['cases'][0]] * 50]:
        with pytest.raises(AssertionError):
            oci_cases({'cases': cases})
    for key, value in [('name', ''), ('valid', None), ('valid', 'false')]:
        changed = [dict(c) for c in corpus['cases']]
        changed[0][key] = value
        with pytest.raises(AssertionError):
            oci_cases({'cases': changed})
