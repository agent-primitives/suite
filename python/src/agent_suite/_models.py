"""Common private records; construction is not package validation."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ._json import Number, decode


@dataclass(frozen=True)
class Source:
    file: str
    pointer: str = ""


@dataclass(frozen=True)
class Diagnostic:
    source: Source
    code: str
    message: str


@dataclass(frozen=True)
class Document:
    data: bytes
    source: Source

    @classmethod
    def from_bytes(cls, data: bytes, source: Source) -> Document:
        if not isinstance(decode(data), dict):
            raise ValueError("document must be an object")
        return cls(data, source)

    @property
    def value(self) -> dict[str, Any]:
        # Original bytes are authoritative; no mutable tree can stale identity.
        value: dict[str, Any] = decode(self.data)
        return value


def _object(value: Any, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("expected object")
    unknown = value.keys() - allowed
    if unknown:
        raise ValueError(f"unknown fields: {sorted(unknown)}")
    return value


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


@dataclass(frozen=True)
class Descriptor:
    media_type: str
    digest: str
    size: int
    annotations: tuple[tuple[str, str], ...] | None = None

    @classmethod
    def from_value(cls, value: Any) -> Descriptor:
        obj = _object(value, {"mediaType", "digest", "size", "annotations"})
        if not {"mediaType", "digest", "size"} <= obj.keys():
            raise ValueError("descriptor missing required field")
        size = obj["size"]
        if not isinstance(size, Number) or not re.fullmatch(r"-?(0|[1-9][0-9]*)", size.lexeme):
            raise ValueError("size must have an integer lexeme")
        integer = int(size.lexeme)
        if not -(1 << 63) <= integer < (1 << 63):
            raise ValueError("size is outside int64")
        annotations = None
        if "annotations" in obj:
            raw = obj["annotations"]
            if not isinstance(raw, dict):
                raise ValueError("annotations must be an object")
            annotations = tuple((k, _string(v, "annotation")) for k, v in raw.items())
        return cls(_string(obj["mediaType"], "mediaType"),
                   _string(obj["digest"], "digest"), integer, annotations)


@dataclass(frozen=True)
class Platform:
    os: str = ""
    architecture: str = ""
    variant: str = ""

    @classmethod
    def from_value(cls, value: Any) -> Platform:
        obj = _object(value, {"os", "architecture", "variant"})
        return cls(**{key: _string(child, key) for key, child in obj.items()})
