"""Copy-on-write naming uses the package's portable collision rules."""
import os

import pytest

from test_capture import extracted, packed_fixture, secure
from test_package import api
from agent_suite._json import digest_bytes


def test_instruction_copy_on_write_avoids_folded_name_collisions(tmp_path, api):
    root, _ = extracted(tmp_path)
    body = b'case-fold collision edit'
    candidate = 'instruction-writer-' + digest_bytes(body)[7:23] + '.md'
    existing = root/candidate.upper()
    existing.write_bytes(b'leave this unrelated file alone')
    secure(root)
    with api.Package(root) as package:
        package.set_instructions('writer', body)
        assert package.validate() == ()
        assert package.agents['writer'].instructions.reference.path != candidate
        assert existing.read_bytes() == b'leave this unrelated file alone'
        assert b''.join(package.agents['writer'].instructions.content.iter_bytes()) == body


@pytest.mark.parametrize('folded', [False, True])
def test_instruction_copy_on_write_reserves_implicit_directories(tmp_path, api, folded):
    root, _ = extracted(tmp_path)
    body = b'implicit directory naming'
    candidate = 'instruction-writer-' + digest_bytes(body)[7:23] + '.md'
    directory = candidate.upper() if folded else candidate
    (root/directory).mkdir()
    (root/directory/'kept.bin').write_bytes(b'keep this payload')
    layout = tmp_path/'layout'
    packed_fixture(root, layout, directories=False)
    secure(layout)
    with api.Package(layout) as package:
        assert directory not in package._content.entries
        package.set_instructions('writer', body)
        assert package.agents['writer'].instructions.reference.path != candidate
        assert package.validate() == ()
        output = package.write_directory(tmp_path/'edited')
        assert (output/directory/'kept.bin').read_bytes() == b'keep this payload'
        with api.Package(package.write_oci(tmp_path/'edited-oci')) as loaded:
            assert loaded.root_digest == package.root_digest


@pytest.mark.parametrize('name', ['D:payload.bin', 'folder/name:stream', 'folder/CON'])
def test_windows_directory_basename_validation(name):
    if os.name != 'nt':
        return
    from agent_suite._content import Entry
    from agent_suite._write import _directory_names
    with pytest.raises(ValueError, match='cannot materialize Windows path'):
        _directory_names([Entry(name)])
