"""Private ordinary evaluation validation, without execution or judge calls."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from ._content import Content
from ._documents import Documents, _at, _pin_json, _require
from ._models import Source
from ._record_decode import read_document
from ._records import EvaluationAssertion, EvaluationCase, EvaluationIndex, Loaded
from ._schema import Bundle

_INDEX = "application/vnd.agentsuite.eval.index.v1+json"
_CASE = "application/vnd.agentsuite.eval.case.v1+json"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,62}")
_KIND = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}")
# Go strings.TrimSpace, deliberately excluding Python's extra U+001C..001F.
_SPACE = "\u0009\u000a\u000b\u000c\u000d\u0020\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"


@dataclass(frozen=True)
class Evaluations:
    index: Loaded[EvaluationIndex]
    cases: tuple[Loaded[EvaluationCase], ...]


def _nonblank(value: str | None) -> bool:
    return value is not None and bool(value.strip(_SPACE))


def _single_line(value: str | None) -> bool:
    return _nonblank(value) and value is not None and all(
        unicodedata.category(c) != "Cc" and c not in "\u2028\u2029" for c in value)


def _assertion(assertion: EvaluationAssertion, valid_regex: Callable[[str], bool]) -> None:
    source = assertion.source
    if assertion.kind in {"contains", "notContains", "toolCalled", "toolNotCalled"}:
        field = "value" if assertion.kind in {"contains", "notContains"} else "tool"
        value = assertion.value if field == "value" else assertion.tool
        _require(_single_line(value), _at(source, field), "evaluation.line",
                 "assertion operand must be nonblank and single-line")
    elif assertion.kind == "regex":
        pattern = assertion.pattern
        _require(pattern is not None and _nonblank(pattern) and len(pattern.encode("utf-8")) <= 1024,
                 _at(source, "pattern"), "evaluation.pattern", "regex must be nonblank and at most 1024 bytes")
        assert pattern is not None
        _require(valid_regex(pattern), _at(source, "pattern"),
                 "evaluation.regex", "regex must use valid Go-compatible RE2 syntax")
    elif assertion.kind == "llmJudge":
        rubric = assertion.rubric
        _require(rubric is not None and _nonblank(rubric) and len(rubric.encode("utf-8")) <= 4096
                 and all(unicodedata.category(c) != "Cc" or c in "\n\t" for c in rubric),
                 _at(source, "rubric"), "evaluation.rubric",
                 "rubric must be nonblank, at most 4096 bytes, and free of controls except LF/TAB")
        _require(assertion.min_score is not None and 0 <= assertion.min_score <= 100,
                 _at(source, "minScore"), "evaluation.score", "minScore must be in 0..100")
        for field, identity in (("judgeModel", assertion.judge_model), ("judgeVersion", assertion.judge_version)):
            _require(identity is not None and _nonblank(identity) and len(identity.encode("utf-8")) <= 256
                     and all(" " <= c <= "~" for c in identity), _at(source, field),
                     "evaluation.judge", "judge identity must be nonblank printable ASCII of at most 256 bytes")
    else:
        _require(_KIND.fullmatch(assertion.kind) and assertion.critical is False, _at(source, "type"),
                 "evaluation.kind", "unknown assertion kind requires explicit critical:false")
        _require(_nonblank(assertion.value), _at(source, "value"),
                 "evaluation.value", "noncritical assertion requires a nonblank value")


def _case(case: EvaluationCase, valid_regex: Callable[[str], bool]) -> None:
    if case.runs is not None:
        _require(case.runs >= 1, _at(case.source, "runs"),
                 "evaluation.runs", "runs must be positive")
    if case.min_passes is not None:
        _require(case.runs is not None and 1 <= case.min_passes <= case.runs, _at(case.source, "minPasses"),
                 "evaluation.min_passes", "minPasses requires runs and must be in 1..runs")
    _require(_nonblank(case.input), _at(case.source, "input"),
             "evaluation.input", "case input must be nonblank")
    _require(1 <= len(case.assertions) <= 1000, _at(case.source, "assertions"),
             "evaluation.assertions", "case requires 1..1000 assertions")
    ids = set()
    for assertion in case.assertions:
        _require(_ID.fullmatch(assertion.id) and assertion.id not in ids, _at(assertion.source, "id"),
                 "evaluation.id", "assertion id must be valid and unique")
        ids.add(assertion.id)
        _assertion(assertion, valid_regex)


def read_evaluations(content: Content, documents: Documents, bundle: Bundle,
                     valid_regex: Callable[[str], bool]) -> dict[str, Evaluations]:
    """Read ordered stored cases using a mandatory private regex syntax validator."""
    result: dict[str, Evaluations] = {}
    files: set[str] = set()
    directories = {"evals"}
    for agent in documents.agents:
        owner = agent.record.id
        refs = agent.record.evals
        _require(len(refs) <= 1, _at(agent.record.source, "evals"),
                 "evaluation.indices", "an agent permits at most one evaluation index")
        if not refs:
            continue
        prefix = f"evals/{owner}"
        directories.update((prefix, prefix + "/cases"))
        ref = refs[0]
        _require(ref.path == prefix + "/index.json", _at(ref.source, "path"),
                 "evaluation.owner", "evaluation index path must match its owning agent")
        index = read_document(_pin_json(content, ref, _INDEX), EvaluationIndex, bundle)
        files.add(ref.path)
        record = index.record
        _require(record.agent == owner, _at(record.source, "agent"),
                 "evaluation.owner", "evaluation index agent must match its owner")
        limits = record.limits
        _require(1 <= limits.max_cases <= 128, _at(limits.source, "maxCases"),
                 "evaluation.limit", "maxCases must be in 1..128")
        _require(1 <= limits.max_case_bytes <= 4194304, _at(limits.source, "maxCaseBytes"),
                 "evaluation.limit", "maxCaseBytes must be in 1..4194304")
        _require(1 <= len(record.cases) <= limits.max_cases, _at(record.source, "cases"),
                 "evaluation.limit", "case count must be nonempty and within maxCases")
        cases = []
        ids = set()
        for case_ref in record.cases:
            case_prefix = prefix + "/cases/"
            _require(case_ref.path.startswith(case_prefix) and case_ref.path.endswith(".json")
                     and "/" not in case_ref.path[len(case_prefix):], _at(case_ref.source, "path"),
                     "evaluation.path", "case must be directly inside its owner's cases directory")
            _require(case_ref.path not in files, _at(case_ref.source, "path"),
                     "evaluation.duplicate", "duplicate evaluation case reference")
            loaded = read_document(_pin_json(content, case_ref, _CASE), EvaluationCase, bundle)
            files.add(case_ref.path)
            _require(len(loaded.document.data) <= limits.max_case_bytes, loaded.document.source,
                     "evaluation.limit", "case exceeds maxCaseBytes")
            case = loaded.record
            _require(_ID.fullmatch(case.id) and case.id not in ids, _at(case.source, "id"),
                     "evaluation.id", "case id must be valid and unique")
            ids.add(case.id)
            _require(case_ref.path == case_prefix + case.id + ".json", _at(case.source, "id"),
                     "evaluation.filename", "case filename must match its id")
            _case(case, valid_regex)
            cases.append(loaded)
        result[owner] = Evaluations(index, tuple(cases))
    for path, entry in content.entries.items():
        if path != "evals" and not path.startswith("evals/"):
            continue
        if entry.kind == "directory" and path in directories:
            continue
        _require(entry.kind == "file" and path in files, Source(path),
                 "evaluation.namespace", "orphaned or nonregular evaluation path")
    return result
