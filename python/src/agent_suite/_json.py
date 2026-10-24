"""Private strict codec. Numeric acceptance mirrors internal/jsoncodec, not I-JSON."""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

import rfc8785

MAX_BYTES = 4 << 20


class Number(float):
    """Binary64 value retaining the original lexeme for typed integer checks."""

    lexeme: str

    def __new__(cls, lexeme: str) -> Number:
        value = super().__new__(cls, lexeme)
        value.lexeme = lexeme
        return value


def _number(lexeme: str) -> Number:
    value = Number(lexeme)
    if not math.isfinite(value):
        raise ValueError("number is not finite binary64")
    # Go compares int64 lexemes exactly; all other lexemes compare as float64.
    # In particular, a fractional spelling can round where an integer cannot.
    if re.fullmatch(r"-?(0|[1-9][0-9]*)", lexeme) and len(lexeme) <= 20:
        integer = int(lexeme)
        if -(1 << 63) <= integer < (1 << 63):
            canonical = rfc8785.dumps(value).decode()
            if not re.fullmatch(r"-?[0-9]+", canonical) or int(canonical) != integer:
                raise ValueError("number value changes during JCS canonicalization")
    return value


def _constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def decode(data: bytes) -> Any:
    """Decode exactly one bounded UTF-8 JSON value without schema/graph checks."""
    if not data or len(data) > MAX_BYTES:
        raise ValueError("document is empty or exceeds 4194304 bytes")
    members = 0

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        nonlocal members
        members += len(items)
        if len(items) > 1024 or members > 100_000:
            raise ValueError("JSON object member limit exceeded")
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            data.decode("utf-8"), object_pairs_hook=pairs,
            parse_int=_number, parse_float=_number, parse_constant=_constant,
        )
        _check_tree(value)
        return value
    except (UnicodeError, RecursionError) as error:
        raise ValueError("invalid Unicode or excessive JSON nesting") from error


def _check_tree(value: Any, depth: int = 0) -> None:
    if isinstance(value, str):
        value.encode("utf-8")
    elif isinstance(value, (dict, list)):
        if depth >= 100:
            raise ValueError("JSON nesting exceeds 100")
        if isinstance(value, dict):
            for key, child in value.items():
                key.encode("utf-8")
                _check_tree(child, depth + 1)
        else:
            for child in value:
                _check_tree(child, depth + 1)


def _jcs_value(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, (str, float)):
        return value
    if isinstance(value, int):
        # rfc8785's Python integer guard is stricter than Go. Apply Go's
        # equivalence check first, then use its binary64 number representation.
        return _number(str(value))
    if isinstance(value, dict):
        return {key: _jcs_value(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_jcs_value(child) for child in value]
    raise ValueError(f"unsupported JSON value type: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    try:
        return rfc8785.dumps(_jcs_value(value))
    except (rfc8785.CanonicalizationError, UnicodeError, RecursionError) as error:
        raise ValueError("cannot canonicalize JSON") from error


def digest_bytes(data: bytes) -> str:
    """Hash literal bytes; callers explicitly choose document/variant/OCI bytes."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def variant_bytes(value: Any) -> bytes:
    if not isinstance(value, dict) or "variantDigest" not in value:
        raise ValueError("variant must contain variantDigest")
    return canonical_bytes({**value, "variantDigest": ""})
