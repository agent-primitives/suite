"""Frozen Go policy boundaries: compact bytes and portable link headers, no extraction."""
import base64
import gzip
import io
import json
import os
import tarfile

import pytest

from agent_suite._json import canonical_bytes, digest_bytes
from test_capture import secure
from test_documents import ROOT
from test_oci import materialize as oci_base
from test_reader_conformance import api, assert_refusal, materialize

CORPUS = json.loads((ROOT / 'testdata/conformance/reader-boundary-cases.json').read_bytes())
ROWS, CONTROLS = CORPUS['cases'], {c['name']: c for c in CORPUS['controls']}


def body(row, entry):
    if entry['type'] != 'file':
        assert entry['bytes'] is None and entry['size'] == 0 and entry['digest'] == ''
        return b''
    if entry['bytes'] is None:
        pattern = row['body']
        assert pattern == dict(path=entry['path'], block='IA==', repeat=4194305)
        raw = base64.b64decode(pattern['block'], validate=True) * pattern['repeat']
    else:
        raw = base64.b64decode(entry['bytes'], validate=True)
    assert len(raw) == entry['size'] and digest_bytes(raw) == entry['digest']
    return raw


def archive(tmp_path, row):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.USTAR_FORMAT) as output:
        for entry in row['entries']:
            header = tarfile.TarInfo(entry['path'])
            header.type = {'file': tarfile.REGTYPE, 'directory': tarfile.DIRTYPE,
                           'symlink': tarfile.SYMTYPE, 'hardlink': tarfile.LNKTYPE}[entry['type']]
            header.mode, header.size, header.linkname = entry['mode'], entry['size'], entry['linkTarget']
            output.addfile(header, io.BytesIO(body(row, entry)))
    # Go permits exactly the required end blocks, not tarfile record padding.
    end = sum(512 + ((e['size'] + 511) // 512) * 512 for e in row['entries']) + 1024
    layer = gzip.compress(buffer.getvalue()[:end], mtime=0)
    layout = tmp_path / row['name']
    oci_base(layout, {'layout': 'minimal-0644'})
    blobs = layout / 'blobs/sha256'
    index = json.loads((layout / 'index.json').read_bytes())
    selected = index['manifests'][0]
    manifest = json.loads((blobs / selected['digest'][7:]).read_bytes())
    manifest['layers'][0].update(size=len(layer), digest=digest_bytes(layer))
    (blobs / digest_bytes(layer)[7:]).write_bytes(layer)
    raw = canonical_bytes(manifest)
    (blobs / digest_bytes(raw)[7:]).write_bytes(raw)
    selected.update(size=len(raw), digest=digest_bytes(raw))
    (layout / 'index.json').write_bytes(canonical_bytes(index))
    return layout


def native(tmp_path, row):
    root = tmp_path / (row['name'] + '-native')
    root.mkdir()
    for entry in row['entries']:
        path = root / entry['path']
        if entry['type'] == 'directory':
            path.mkdir(parents=True, exist_ok=True)
        elif entry['type'] == 'symlink':
            path.symlink_to(entry['linkTarget'])
        else:
            assert entry['type'] == 'file'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body(row, entry))
    secure(root)
    return root


@pytest.mark.parametrize('row', ROWS, ids=lambda row: row['name'])
def test_shared_reader_boundary_cases(tmp_path, api, row):
    Package, LoadError = api
    assert len(ROWS) == 5 and set(CONTROLS) == {'policy-boundary-base', 'policy-hardlink-control'}
    assert {r['name'] for r in ROWS} == {'policy-oversized', 'policy-symlink-root', 'policy-symlink-writer',
                                      'policy-symlink-extra', 'policy-hardlink-writer'}
    assert row['valid'] is False and row['phase'] == 'ValidatePath' and row['refusal']
    assert row['origin'].startswith('d753475d3313507bb3297d06b28ec373287e3791:')
    control = CONTROLS[row['control']]
    materialize(tmp_path / 'control', control)
    with Package.load(tmp_path / 'control'):
        pass
    with Package.load(archive(tmp_path, control)):
        pass
    with pytest.raises(LoadError) as error:
        Package.load(archive(tmp_path, row))
    assert_refusal(error,row['name'])
    if row['body'] is not None:
        with pytest.raises(LoadError) as error:
            Package.load(native(tmp_path, row))
        assert_refusal(error,row['name'])


if os.name != 'nt':
    @pytest.mark.parametrize('row', [r for r in ROWS if r['name'].startswith('policy-symlink-')], ids=lambda row: row['name'])
    def test_shared_reader_boundary_native_symlinks(tmp_path, api, row):
        Package, LoadError = api
        with pytest.raises(LoadError) as error:
            Package.load(native(tmp_path, row))
        assert_refusal(error,row['name'])
