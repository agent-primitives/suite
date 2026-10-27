"""Validated directory and local OCI packages with self-contained literal views."""
from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from ._capture import capture_directory, capture_oci_layout
from ._content import Content
from ._directory import load_directory
from ._evaluations import Evaluations, read_evaluations
from ._graph import GraphParts, read_graph
from ._json import canonical_bytes, digest_bytes
from ._literals import LiteralContent, LiteralSnapshot
from ._models import Diagnostic, Document, Source
from ._oci import load_oci_layout
from ._policies import read_policies
from ._record_decode import DocumentError
from ._records import (
    Agent, BuildProfile, Composition, EvaluationAssertion, EvaluationCase, EvaluationIndex, FileRef, Loaded,
    PolicyV1, PolicyV2, RuntimeProfile, Suite, Tool, ToolProvider, ToolProviderComposition,
)
from ._schema import Bundle


class LoadError(DocumentError):
    """Contextual format/graph or I/O refusal, with diagnostics and original cause."""


def _valid_regex(pattern: str) -> bool:
    # Syntax checking only, with the pinned native adapter and no Python-re fallback.
    from ._regex import valid
    return valid(pattern)


@dataclass(frozen=True)
class LiteralView:
    reference: FileRef
    content: LiteralContent

    @property
    def source(self) -> Source:
        return self.reference.source


@dataclass(frozen=True)
class PolicyView:
    reference: FileRef
    document: Document
    declaration: PolicyV1 | PolicyV2

    @property
    def source(self) -> Source:
        return self.declaration.source


@dataclass(frozen=True)
class CaseView:
    document: Document
    declaration: EvaluationCase

    @property
    def source(self) -> Source:
        return self.declaration.source

    @property
    def assertions(self) -> tuple[EvaluationAssertion, ...]:
        return self.declaration.assertions


@dataclass(frozen=True)
class EvaluationIndexView:
    document: Document
    declaration: EvaluationIndex
    cases: tuple[CaseView, ...]

    @property
    def source(self) -> Source:
        return self.declaration.source


@dataclass(frozen=True)
class ToolView:
    declaration: Tool
    input_schema: LiteralView
    output_schema: LiteralView | None

    @property
    def source(self) -> Source:
        return self.declaration.source


@dataclass(frozen=True)
class ProviderView:
    document: Document
    declaration: ToolProvider
    tools: tuple[ToolView, ...]

    @property
    def source(self) -> Source:
        return self.declaration.source


@dataclass(frozen=True)
class AgentView:
    document: Document
    declaration: Agent
    instructions: LiteralView
    policy: PolicyView | None
    evaluations: EvaluationIndexView | None

    @property
    def source(self) -> Source:
        return self.declaration.source


def _evaluation_view(value: Evaluations) -> EvaluationIndexView:
    return EvaluationIndexView(value.index.document, value.index.record,
                               tuple(CaseView(c.document, c.record) for c in value.cases))


def _load_content(raw: str) -> Content:
    root = Path(raw)
    if not stat.S_ISDIR(root.stat().st_mode):
        raise ValueError('package input must be an extracted directory or local OCI layout directory')
    try:
        (root / 'oci-layout').lstat()
    except FileNotFoundError:
        return load_directory(raw)
    return load_oci_layout(raw)


@dataclass(frozen=True, init=False, eq=False, repr=False)
class Package:
    _content: Content
    _bundle: Bundle
    _parts: GraphParts
    _snapshot: LiteralSnapshot
    suite: Loaded[Suite]
    agents: Mapping[str, AgentView]
    tool_providers: Mapping[tuple[str, str], ProviderView]
    root_digest: str
    artifact_digest: str | None

    def __init__(self, path: str | os.PathLike[str]) -> None:
        snapshot = None
        raw = '<input>'
        try:
            candidate = os.fspath(path)
            if not isinstance(candidate, str):
                raise TypeError('package input must resolve to a text path')
            raw = candidate
            if not raw:
                raise ValueError('package input must be a nonempty text path')
            bundle = Bundle.installed()
            content = _load_content(raw)
            parts = read_graph(content, bundle)
            documents = parts.documents
            policies = read_policies(content, documents, bundle)
            evaluations = read_evaluations(content, documents, bundle, _valid_regex)
            capture = capture_directory if content.source_type == 'directory' else capture_oci_layout
            snapshot = capture(raw, content, documents)
            agents = {}
            for loaded in documents.agents:
                agent = loaded.record
                policy = policies.get(agent.id)
                binding = None
                if policy is not None:
                    assert agent.policy is not None
                    binding = PolicyView(agent.policy, policy.document, policy.record)
                agents[agent.id] = AgentView(loaded.document, agent,
                    LiteralView(agent.instructions, snapshot.get(agent.instructions)), binding,
                    _evaluation_view(evaluations[agent.id]) if agent.id in evaluations else None)
            providers = {}
            for loaded_provider in documents.providers:
                provider = loaded_provider.record
                tools = tuple(ToolView(tool, LiteralView(tool.input_schema, snapshot.get(tool.input_schema)),
                    LiteralView(tool.output_schema, snapshot.get(tool.output_schema))
                    if tool.output_schema is not None else None) for tool in provider.tools)
                providers[(provider.id, provider.version)] = ProviderView(loaded_provider.document, provider, tools)
            # Capture has matched every literal before this identity becomes visible.
            root_digest = digest_bytes(canonical_bytes(documents.suite.document.value))
            object.__setattr__(self, '_content', content)
            object.__setattr__(self, '_bundle', bundle)
            object.__setattr__(self, '_parts', parts)
            object.__setattr__(self, '_snapshot', snapshot)
            object.__setattr__(self, 'suite', documents.suite)
            object.__setattr__(self, 'agents', MappingProxyType(agents))
            object.__setattr__(self, 'tool_providers', MappingProxyType(providers))
            object.__setattr__(self, 'root_digest', root_digest)
            object.__setattr__(self, 'artifact_digest', content.artifact_digest or None)
        except BaseException as error:
            if snapshot is not None:
                with suppress(OSError):
                    snapshot.close()
            if isinstance(error, DocumentError):
                raise LoadError(error.diagnostics) from error
            if isinstance(error, (OSError, ValueError, TypeError)):
                code = 'load.io' if isinstance(error, OSError) else 'load.content'
                raise LoadError((Diagnostic(Source(raw), code, str(error)),)) from error
            raise

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> Package:
        return cls(path)

    @property
    def build_profiles(self) -> tuple[Loaded[BuildProfile], ...]:
        return self._parts.build_profiles

    @property
    def runtime_profiles(self) -> tuple[Loaded[RuntimeProfile], ...]:
        return self._parts.runtime_profiles

    @property
    def compositions(self) -> tuple[Loaded[Composition], ...]:
        return self._parts.compositions

    @property
    def tool_provider_compositions(self) -> tuple[Loaded[ToolProviderComposition], ...]:
        return self._parts.tool_provider_compositions

    def validate(self) -> tuple[Diagnostic, ...]:
        if self._snapshot.closed:
            raise ValueError('package is closed')
        try:
            parts = read_graph(self._content, self._bundle)
            read_policies(self._content, parts.documents, self._bundle)
            read_evaluations(self._content, parts.documents, self._bundle, _valid_regex)
            refs = [a.record.instructions for a in parts.documents.agents]
            for provider in parts.documents.providers:
                for tool in provider.record.tools:
                    refs.append(tool.input_schema)
                    if tool.output_schema is not None:
                        refs.append(tool.output_schema)
            for ref in refs:
                digest = hashlib.sha256()
                size = 0
                for chunk in self._snapshot.get(ref).iter_bytes():
                    digest.update(chunk)
                    size += len(chunk)
                if size != ref.descriptor.size or 'sha256:' + digest.hexdigest() != ref.descriptor.digest:
                    return (Diagnostic(ref.source, 'snapshot.pin', 'retained literal bytes do not match pin'),)
        except DocumentError as error:
            return error.diagnostics
        except (OSError, ValueError) as error:
            return (Diagnostic(Source('<snapshot>'), 'snapshot.read', str(error)),)
        return ()

    def close(self) -> None:
        try:
            self._snapshot.close()
        finally:
            # Normative documents remain in the public frozen views. Do not keep
            # unused metadata/literal JSON buffers in private Content after close.
            self._content.entries.clear()

    def __enter__(self) -> Package:
        if self._snapshot.closed:
            raise ValueError('package is closed')
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
