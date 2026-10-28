"""Generated typed-envelope probes run against the actual private Go loader."""
import base64
import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path

from test_oci import ROOT, materialize, snapshot

ORACLE_ROOT = Path(os.environ.get('AGENTSUITE_GO_ORACLE_ROOT', str(ROOT))).resolve()


def test_go_oci_differential(tmp_path):
    from agent_suite._oci import load_oci_layout
    base = ROOT / 'testdata/conformance/oci/minimal-0644'
    index = json.loads((base / 'index.json').read_bytes())
    original = json.loads((base / 'blobs/sha256' / index['manifests'][0]['digest'][7:]).read_bytes())
    probes = []

    def add(manifest, idx=None):
        raw = manifest if isinstance(manifest, bytes) else json.dumps(manifest, separators=(',', ':')).encode()
        digest = hashlib.sha256(raw).hexdigest()
        idx = copy.deepcopy(index if idx is None else idx)
        idx['manifests'][0].update(digest='sha256:' + digest, size=len(raw))
        files = {'blobs/sha256/' + digest: base64.b64encode(raw).decode(),
                 'index.json': base64.b64encode(json.dumps(idx).encode()).decode()}
        probes.append(dict(name='probe-' + str(len(probes)), layout='minimal-0644', files=files))

    values = [None, '', {}, [], True, 0, 2, 2.0, '2', -1, {'a': None}, {'a': ''}]
    for field in ['schemaVersion', 'mediaType', 'artifactType', 'config', 'layers', 'subject', 'annotations', 'unknown']:
        for value in values:
            man = copy.deepcopy(original)
            man[field] = value
            add(man)
    for position in ['index', 'config', 'layer']:
        for field in ['mediaType', 'digest', 'size', 'artifactType', 'data', 'urls', 'platform', 'annotations']:
            for value in values:
                man, idx = copy.deepcopy(original), copy.deepcopy(index)
                d = idx['manifests'][0] if position == 'index' else man['config'] if position == 'config' else man['layers'][0]
                d[field] = value
                # add() must repin the manifest, so index digest/size probes are
                # covered instead by the fixed byte-exact corpus.
                if position == 'index' and field in ('digest', 'size'):
                    continue
                add(man, idx)
    for lexeme in ['-0', '0.0', '2e0', '9007199254740993', '9223372036854775807', '9223372036854775808']:
        raw = json.dumps(original).replace('"schemaVersion": 2', '"schemaVersion": ' + lexeme).encode()
        add(raw)
    layer = (base / 'blobs/sha256' / original['layers'][0]['digest'][7:]).read_bytes()
    man = copy.deepcopy(original)
    man['layers'][0]['data'] = [None if value == 0 else value for value in layer]
    add(man)
    for value in ['e30=', 'e31=', 'e3\r\n0=', 'e30', 'e30==', 'e30=\n', 'e3 0=', '====', 'e30=AAAA', '', []]:
        man = copy.deepcopy(original)
        man['config']['data'] = value
        add(man)
    for lexeme in ['-0', '0.0', '0e0', '256', 'null', 'false']:
        man = copy.deepcopy(original)
        man['layers'][0]['data'] = list(layer)
        raw = json.dumps(man, separators=(',', ':')).replace('"data":[31,139,8,0,', '"data":[31,139,8,' + lexeme + ',', 1).encode()
        add(raw)
    requests = tmp_path / 'requests.json'
    requests.write_text(json.dumps(probes), encoding='utf-8')
    executable = tmp_path / ('oracle.exe' if os.name == 'nt' else 'oracle')
    subprocess.run(['go', 'test', '-c', '-o', str(executable), './internal/artifact'], cwd=ORACLE_ROOT, check=True)
    subprocess.run([str(executable), '-test.run=^TestSharedOCICases$'], cwd=ORACLE_ROOT / 'internal/artifact', check=True,
                   env={**os.environ, 'AGENTSUITE_OCI_ORACLE': str(requests)}, capture_output=True, timeout=60)
    expected = json.loads(Path(str(requests) + '.result').read_bytes())
    mismatches = []
    for case in expected:
        root = tmp_path / case['name']
        materialize(root, case)
        try:
            content = load_oci_layout(root)
            result = snapshot(content)
        except (ValueError, OSError):
            result = None
        if ((result is not None) != case['valid'] or case['valid'] and
                (result != case.get('entries', []) or content.artifact_digest != case['artifactDigest'])):
            mismatches.append((case['name'], case.get('error'), result))
    assert not mismatches, mismatches[:10]
    assert len(expected) >= 350
