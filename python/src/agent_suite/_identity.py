"""Separate document, variant and exact OCI byte identities."""
from typing import Any

from ._json import canonical_bytes, digest_bytes, variant_bytes


def digest(value: Any) -> str:
    """SHA-256 of RFC 8785 canonical JSON, not an OCI artifact identity."""
    return digest_bytes(canonical_bytes(value))


def variant_digest(value: Any) -> str:
    """Hash canonical JSON with only the top-level variantDigest blanked."""
    return digest_bytes(variant_bytes(value))


def oci_manifest_digest(manifest_bytes: bytes) -> str:
    """Hash exact stored manifest bytes without parsing or normalization."""
    if not isinstance(manifest_bytes, bytes):
        raise TypeError('manifest_bytes must be bytes')
    return digest_bytes(manifest_bytes)
