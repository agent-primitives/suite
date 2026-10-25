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
