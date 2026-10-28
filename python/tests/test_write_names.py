"""Copy-on-write naming uses the package's portable collision rules."""
from test_capture import extracted, secure
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
