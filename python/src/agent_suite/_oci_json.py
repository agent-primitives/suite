"""Private OCI typed decoding; deliberately not core content descriptors."""
from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from typing import Any

from ._json import Number, decode, digest_bytes
from ._models import Platform, _object, _string

ARTIFACT = "application/vnd.agentsuite.suite.v1"
CONTENT = "application/vnd.agentsuite.content.v1.tar+gzip"
EMPTY_CONFIG = "application/vnd.oci.empty.v1+json"
MANIFEST = "application/vnd.oci.image.manifest.v1+json"
INDEX = "application/vnd.oci.image.index.v1+json"


def _integer(value: Any) -> int:
    if not isinstance(value, Number) or not re.fullmatch(r"-?(0|[1-9][0-9]*)", value.lexeme):
        raise ValueError("OCI integer must have an integer lexeme")
    if len(value.lexeme) > 20 or not -(1 << 63) <= int(value.lexeme) < (1 << 63):
        raise ValueError("OCI integer is outside int64")
    return int(value.lexeme)


def _annotations(obj: dict[str, Any]) -> None:
    annotations = obj.get("annotations")
    if annotations is not None:
        if not isinstance(annotations, dict):
            raise ValueError("OCI annotations must be an object")
        for value in annotations.values():
            _string(value, "annotation")


def _embedded(value: Any) -> bytes:
    if isinstance(value, str):
        raw = value.replace("\r", "").replace("\n", "")
        # Older binascii strict decoders allow surplus '=' after full quanta.
        if len(raw) % 4 or raw.endswith("==="):
            raise ValueError("descriptor data must use padded base64")
        try:
            return base64.b64decode(raw, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("invalid descriptor base64 data") from error
    if isinstance(value, list):
        # encoding/json []byte accepts numeric arrays; null elements become 0.
        values = []
        for item in value:
            integer = 0 if item is None else _integer(item)
            if not 0 <= integer <= 255 or isinstance(item, Number) and item.lexeme.startswith("-"):
                raise ValueError("descriptor data byte is outside uint8")
            values.append(integer)
        return bytes(values)
    raise ValueError("descriptor data must be base64 or a byte array, not null")


@dataclass(frozen=True)
class Descriptor:
    media_type: str = ""
    digest: str = ""
    size: int = 0
    artifact_type: str = ""
    data: bytes | None = None
    urls: bool = False

    def validate(self) -> None:
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.digest) or self.size < 0:
            raise ValueError("descriptor digest or size is invalid")
        if self.urls:
            raise ValueError("descriptor urls are not allowed")
        if self.data is not None and (len(self.data) != self.size or digest_bytes(self.data) != self.digest):
            raise ValueError("descriptor data does not match digest and size")


def descriptor(value: Any) -> Descriptor:
    obj = _object(value, {"mediaType", "digest", "size", "data", "urls", "artifactType", "platform", "annotations"})
    _annotations(obj)
    if obj.get("platform") is not None:
        Platform.from_value(obj["platform"])
    return Descriptor(
        _string(obj.get("mediaType", ""), "mediaType"), _string(obj.get("digest", ""), "digest"),
        _integer(obj["size"]) if "size" in obj else 0,
        _string(obj.get("artifactType", ""), "artifactType"),
        _embedded(obj["data"]) if "data" in obj else None, "urls" in obj,
    )


def _descriptors(value: Any) -> list[Descriptor]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("OCI descriptors must be an array")
    return [descriptor(item) for item in value]


def layout(data: bytes) -> None:
    obj = _object(decode(data), {"imageLayoutVersion"})
    if _string(obj.get("imageLayoutVersion", ""), "imageLayoutVersion") != "1.0.0":
        raise ValueError("oci-layout imageLayoutVersion must be 1.0.0")


def index(data: bytes) -> list[Descriptor]:
    obj = _object(decode(data), {"schemaVersion", "mediaType", "manifests", "annotations"})
    _annotations(obj)
    descriptors = _descriptors(obj.get("manifests"))
    version = _integer(obj["schemaVersion"]) if "schemaVersion" in obj else 0
    if version != 2 or _string(obj.get("mediaType", ""), "mediaType") not in ("", INDEX):
        raise ValueError("index.json is not an OCI image index")
    return descriptors


def manifest(data: bytes) -> tuple[Descriptor, Descriptor]:
    obj = _object(decode(data), {"schemaVersion", "mediaType", "artifactType", "config", "layers", "subject", "annotations"})
    _annotations(obj)
    config = descriptor(obj.get("config", {}))
    layers = _descriptors(obj.get("layers"))
    if obj.get("subject") is not None:
        descriptor(obj["subject"])
        raise ValueError("AgentSuite manifest must not use subject")
    version = _integer(obj["schemaVersion"]) if "schemaVersion" in obj else 0
    if (version != 2 or _string(obj.get("mediaType", ""), "mediaType") not in ("", MANIFEST)
            or _string(obj.get("artifactType", ""), "artifactType") != ARTIFACT):
        raise ValueError("OCI manifest is not an AgentSuite artifact")
    if config.media_type != EMPTY_CONFIG or len(layers) != 1 or layers[0].media_type != CONTENT:
        raise ValueError("AgentSuite manifest requires an empty config and one content layer")
    return config, layers[0]
