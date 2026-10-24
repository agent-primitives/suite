"""Schema-only diagnostics over an explicit closed registry, never graph validation."""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable

from ._json import decode, digest_bytes
from ._models import Diagnostic, Source


@dataclass(frozen=True)
class Bundle:
    schemas: Mapping[str, Any]
    registry: Registry[Any]

    @classmethod
    def from_bytes(cls, documents: Mapping[str, bytes]) -> Bundle:
        schemas: dict[str, Any] = {}
        resources = []
        seen = set()
        for name, data in sorted(documents.items()):
            schema = decode(data)
            Draft202012Validator.check_schema(schema)
            identity = schema["$id"]
            if identity in seen:
                raise ValueError(f"duplicate schema identity: {identity}")
            seen.add(identity)
            schemas[name] = schema
            resources.append((identity, Resource.from_contents(schema)))
        # Registry's default retriever refuses unknown resources; no HTTP fallback.
        return cls(schemas, Registry().with_resources(resources))

    @classmethod
    def installed(cls) -> Bundle:
        root = files("agent_suite").joinpath("_schemas")
        inventory = json.loads(root.joinpath("provenance.json").read_bytes())
        documents = {}
        names = {p.name for p in root.iterdir() if p.name.endswith(".schema.json")}
        if names != set(inventory["schemas"]):
            raise ValueError("schema bundle inventory mismatch")
        for name, expected in inventory["schemas"].items():
            data = root.joinpath(name).read_bytes()
            if digest_bytes(data) != expected["digest"]:
                raise ValueError(f"schema bundle digest mismatch: {name}")
            if json.loads(data)["$id"] != expected["id"]:
                raise ValueError(f"schema bundle identity mismatch: {name}")
            documents[name] = data
        return cls.from_bytes(documents)

    def validate(self, name: str, value: Any, source: Source) -> list[Diagnostic]:
        validator = Draft202012Validator(self.schemas[name], registry=self.registry)
        try:
            errors = list(validator.iter_errors(value))
        except Unresolvable as error:
            raise ValueError(f"unresolved offline schema reference in {name}") from error
        return [
            Diagnostic(
                Source(source.file, source.pointer + "".join(
                    "/" + str(part).replace("~", "~0").replace("/", "~1")
                    for part in error.absolute_path
                )),
                "schema." + str(error.validator),
                error.message,
            )
            for error in errors
        ]
