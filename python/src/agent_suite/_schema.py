"""Schema-only diagnostics over an explicit closed registry, never graph validation."""
from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, ValidationError, validators
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012
from referencing.exceptions import Unresolvable

from ._json import decode, digest_bytes
from ._models import Diagnostic, Source
from ._schema_uniqueness import Validator


def _format_pattern(validator: Any, pattern: str, value: Any, schema: Any) -> Iterator[ValidationError]:
    # Go's reference schema engine uses an ASCII Perl whitespace class, without
    # VT. Python re (including re.ASCII) gives this exact asset pattern a different
    # meaning. This is schema matching, never execution of an evaluation pattern.
    if pattern == r'\S':
        if validator.is_type(value, 'string') and re.search(r'[^\t\n\f\r ]', value) is None:
            yield ValidationError(f'{value!r} does not match {pattern!r}')
    else:
        yield from Draft202012Validator.VALIDATORS['pattern'](validator, pattern, value, schema)


_SuiteValidator = validators.extend(Validator, {'pattern': _format_pattern})


def _check_references(resource: Resource[Any], resolver: Any) -> None:
    # Visit schema subresources, not instance data in examples/const/default.
    contents = resource.contents
    if isinstance(contents, dict):
        for keyword in ("$ref", "$dynamicRef"):
            if keyword in contents:
                resolver.lookup(contents[keyword])
    for child in resource.subresources():
        _check_references(child, resolver.in_subresource(child))


def _no_nested_dialect(value: Any) -> bool:
    # A JSON Pointer can reach schemas under unknown keywords too. Conservatively
    # retain stock behavior even for schema-looking literal data; never rewrite it.
    if isinstance(value, dict):
        return '$schema' not in value and all(_no_nested_dialect(child) for child in value.values())
    if isinstance(value, list):
        return all(_no_nested_dialect(child) for child in value)
    return True


@dataclass(frozen=True)
class Bundle:
    schemas: Mapping[str, Any]
    registry: Registry[Any]
    _validation_schemas: Mapping[str, Any] | None = field(default=None, repr=False, compare=False)
    _validation_registry: Registry[Any] | None = field(default=None, repr=False, compare=False)

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
        registry = Registry().with_resources(resources).crawl()
        try:
            for identity, resource in resources:
                _check_references(resource, registry.resolver(identity))
        except Unresolvable as error:
            raise ValueError("unresolved offline schema reference in bundle") from error
        # Explicit dialect declarations make jsonschema.evolve select the stock
        # class again across references. Local views keep this equivalent keyword
        # extension active without registering or modifying a global validator.
        if all(validators.validator_for(schema, default=None) is Draft202012Validator
               for schema in schemas.values()) and all(
                   _no_nested_dialect(child) for schema in schemas.values()
                   for key, child in schema.items() if key != '$schema'):
            views = {name: {k: v for k, v in schema.items() if k != '$schema'}
                     for name, schema in schemas.items()}
            view_registry = Registry().with_resources(
                (view['$id'], Resource.from_contents(view, default_specification=DRAFT202012)) for view in views.values()
            ).crawl()
            try:
                for identity, resource in view_registry.items():
                    _check_references(resource, view_registry.resolver(identity))
            except Unresolvable:
                # A reference into removed dialect metadata must keep the original
                # registry/validator, as must mixed or nested-dialect bundles above.
                pass
            else:
                return cls(schemas, registry, views, view_registry)
        return cls(schemas, registry)

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
        if self._validation_schemas is not None and self._validation_registry is not None:
            kind = _SuiteValidator if all(schema['$id'].startswith('https://suite.agent-primitives.dev/schema/')
                                           for schema in self.schemas.values()) else Validator
            validator = kind(self._validation_schemas[name], registry=self._validation_registry)
        else:
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
                f"schema constraint {error.validator} failed",
            )
            for error in errors
        ]
