"""Go/native acceptance, never expression matching or a runtime Go fallback."""
import json
import os
from pathlib import Path
import random
import subprocess
import sys

import pytest
import re2

ROOT = Path(__file__).resolve().parents[2]


def _corpus():
    def unique(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, key
            result[key] = value
        return result

    corpus = json.loads((ROOT / "testdata/conformance/regex-cases.json").read_bytes(),
                        object_pairs_hook=unique)
    assert set(corpus) == {"cases"}
    names = set()
    for row in corpus["cases"]:
        assert set(row) == {"name", "pattern", "valid"}
        assert type(row["valid"]) is bool
        assert isinstance(row["name"], str) and row["name"] and row["name"] not in names
        assert isinstance(row["pattern"], str)
        assert len(row["pattern"].encode("utf-8")) <= 1024
        names.add(row["name"])
    assert len(names) == 702
    assert {"empty", "named-unicode", "named-digit", "byte-escape", "byte-quoted",
            "byte-after-posix", "property-spaces", "property-Old_Italic-exact",
            "property-SignWriting-exact", "property-Assigned-exact",
            "repeat-nested-over", "repeat-zero-barrier", "repeat-zero-invalid-inner",
            "repeat-zero-nested", "budget-literal", "budget-letter",
            "budget-folded-nonword", "budget-dotall", "budget-complement",
            "budget-quoted-utf8", "budget-nullable-range", "budget-anchor-star",
            "repeat-range-nested-over", "repeat-range-nested-zero-barrier",
            "repeat-range-min-leading-zero", "repeat-range-bare-flags",
            "class-hex-range-reversed", "class-hex-range-then-invalid-posix",
            "class-octal-range-then-invalid-posix", "class-braced-hex-range-then-invalid-posix",
            "nul", "newline", "vt", "nel", "nbsp", "bom"} <= names
    return corpus["cases"]


def test_shared_regex_cases():
    from agent_suite._regex import valid

    for row in _corpus():
        assert valid(row["pattern"]) is row["valid"], row


def test_native_regex_budget_and_cache_isolation():
    from agent_suite._regex import valid

    # Characterize the pinned binding's real default-budget incompatibility.
    options = re2.Options()
    options.log_errors = False
    compiled = re2._re2.RE2(rb"(\pL){1000}", options)
    assert not compiled.ok() and b"compile failed" in compiled.error()
    cached = re2.compile("consumer-owned-cached-expression")
    before = re2._Regexp._make.cache_info()
    for row in _corpus():
        assert valid(row["pattern"]) is row["valid"], row["name"]
    assert re2._Regexp._make.cache_info() == before
    assert cached.pattern == "consumer-owned-cached-expression"


def test_native_regex_compiles_bounded_syntax(monkeypatch):
    from agent_suite._regex import valid

    native = re2._re2.RE2
    calls = []

    def measured(pattern, options):
        compiled = native(pattern, options)
        calls.append((pattern, compiled.ProgramSize()))
        return compiled

    monkeypatch.setattr(re2._re2, "RE2", measured)
    for row in _corpus():
        if not row["name"].startswith("budget-"):
            continue
        calls.clear()
        assert valid(row["pattern"]), row["name"]
        # UTF-8 byte-range expansion must not multiply through outer repeats.
        assert calls[-1][0].isascii(), row["name"]
        # A bounded program or parse-success certificate, never a full large
        # matching program (anchor/star lowering exceeds 2.5M instructions).
        assert calls[-1][1] == -1 or 0 < calls[-1][1] <= 4096, (row["name"], calls[-1])
        if row["name"] in ("budget-nullable-range", "budget-anchor-star"):
            assert calls[-1][1] == -1, row["name"]
    calls.clear()
    assert valid(r"(?i:([\W\pL[:alpha:]\x{100}-\x{ffff}]){1000})")
    class_calls = [p for p, _ in calls if p.startswith(b"[")]
    assert class_calls == [rb"[\W\p{Any}[:alpha:]\x{100}-\x{ffff}]"]
    assert calls[-1][0] == b"(?i:(a){1000})"
    calls.clear()
    assert valid("[[-[:bad:]")
    assert [p for p, _ in calls if p.startswith(b"[")] == [rb"[[-\[:bad:]"]
    assert calls[-1][0] == b"a"
    assert not valid("[[:bad:]]")


def test_native_regex_bounded_range_cpu(monkeypatch):
    # Removing the bounded compiler budget must fail in a fresh process, not
    # merely return the right acceptance result after tens of seconds of work.
    script = '''
import time
from agent_suite._regex import valid
start = time.monotonic()
for pattern in ("a{0,1000}" * 113, "(" + "^*" * 507 + "){1000}",
                "(?:a?){0,1000}" * 55, "a?" * 512):
    assert valid(pattern)
print(time.monotonic() - start)
'''
    child = subprocess.run([sys.executable, "-c", script], cwd=ROOT, check=True,
                           text=True, capture_output=True, timeout=5)
    assert float(child.stdout) < 5

    from agent_suite._regex import valid

    native = re2._re2.RE2
    calls = []

    def measured(pattern, options):
        calls.append(pattern)
        return native(pattern, options)

    monkeypatch.setattr(re2._re2, "RE2", measured)
    assert valid("a{0,1000}" * 113)
    # Portable guard: the original counts reach the native parser unchanged;
    # its program budget aborts compilation, after full syntax validation.
    assert calls == [b"a{0,1000}" * 113]


def test_native_regex_peak_memory():
    # A fresh process avoids both binding caches and an earlier RSS high-water
    # mark. The portable program-size guard above also runs on Windows.
    if os.name == "nt":
        return
    script = r'''
import json, resource, sys, time
from agent_suite._regex import valid
patterns = json.load(sys.stdin)
start = time.monotonic()
for pattern in patterns:
    assert valid(pattern)
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
if sys.platform != "darwin":
    peak *= 1024
print(json.dumps({"peak_bytes": peak, "seconds": time.monotonic() - start}))
'''
    patterns = [row["pattern"] for row in _corpus()
                if row["name"].startswith("budget-")]
    child = subprocess.run([sys.executable, "-c", script], cwd=ROOT, check=True,
                           input=json.dumps(patterns), text=True, capture_output=True,
                           timeout=120)
    usage = json.loads(child.stdout)
    assert 0 < usage["peak_bytes"] < 256 * 1024 * 1024, usage


def test_go_regex_differential(tmp_path):
    from agent_suite._regex import valid

    rng = random.Random(26102)
    atoms = ["a", ".", "[a-z]", "[^a]", r"\pL", r"\p{Assigned}",
             r"\p{Old_Italic}", r"\p{UPPERCASE LETTER}", r"\C",
             r"\\C", r"\Q\C\E", "(?<é>a)", "(?<1>a)", r"\123",
             "[]a]", "[[:alpha:]]", r"[\pL-a]", r"[a-\pL]", ""]
    wrappers = ["{}", "({})", "(?:{})", "(?i:{})", "[{}]", r"\Q{}\E"]
    repeats = ["", "*", "+?", "{0}", "{2}", "{10}", "{1001}", "{01}"]
    patterns = [rng.choice(wrappers).format(rng.choice(atoms)) +
                rng.choice(repeats) + rng.choice(["", "|a", rng.choice(atoms)])
                for _ in range(3000)]
    patterns += ["((" + atom + "{" + str(inner) + "}){0}){" + str(outer) + "}"
                 for atom in ("a", r"\pL", "(?i:a)", "[a-z]")
                 for inner in (1, 10, 100, 1000, 1001)
                 for outer in (2, 10, 100, 1000, 1001)]
    # Exercise the class/escape reduction boundary, including malformed ranges,
    # first ']', POSIX nesting, quoted syntax and Unicode escape endpoints.
    class_atoms = ["a", "z", "]", "-", "^", "[", "[:alpha:]", "[:bad:]",
                   "[:alpha", r"\W", r"\w", r"\D", r"\S", r"\pL", r"\P{Any}",
                   r"\p{Cs}", r"\p{Cn}", r"\x{ffff}", r"\x{10000}", r"\x{D800}",
                   r"\x{110000}", r"\x7", r"\123", r"\1", r"\C", r"\Q", r"\]", "é"]
    for _ in range(6000):
        left, right = rng.choices(class_atoms, k=2)
        atom = "[" + rng.choice(["", "^", "]", "^]"]) + left + rng.choice(["", "-"]) + right
        atom += rng.choice(["]", "", "]]"])
        patterns.append(rng.choice(["{}", "(?i:{})", "({}){1000}", "({}){0}",
                                    "(({}){100}){11}", r"\Q{}\E"]).replace("{}", atom))
    # Parse certification must preserve Go's lexical, structural and nested
    # repeat decisions, not just standalone count acceptance.
    range_atoms = ["a", "", "^", "$", r"\b", "(?i)", "a(?i)", "(?i:a)",
                   "()", "(?:)", "(?<1>a)", "(?<é>a)", r"\p{Assigned}",
                   r"\p{Old_Italic}", r"\C", r"\Qa{0,2}\E", r"a\{0,2\}",
                   "[{0,2}]", r"[\pL]", "[[-[:bad:]"]
    range_tokens = ["{0,1}", "{0,2}", "{1,2}", "{2,3}", "{0,1000}",
                    "{1,1000}", "{2,1001}", "{1001,1000}", "{1,0}", "{0,0}",
                    "{01,2}", "{0,01}", "{000,1001}", "{0,}", "{2,}",
                    "{١,٢}", "{0,2x}", "{0,,2}", "{,2}", "{0,2}{0,2}",
                    "{0,2}?", "{0,2}??", "{0,2}+", "{0,2}*", "{0,2}{2}",
                    "{999999999999999999999}", "{0,999999999999999999999}",
                    "{999999999999999999999,}", "{01,999999999999999999999}"]
    for atom in range_atoms:
        for token in range_tokens:
            expression = atom + token
            for wrapper in ("{}", "({}){0}", "({}){0,0}", "({}){0,2}",
                            "({}){0,1000}", "({}){2,}", "(?i:{})", r"\Q{}\E"):
                patterns.append(wrapper.replace("{}", expression))
    # Escaped range endpoints must consume one whole rune before a following
    # hyphen/POSIX atom; include malformed, scalar and class-valued endpoints.
    for escape in (r"\x41", r"\x{41}", r"\x{0041}", r"\101", r"\0", r"\01"):
        for suffix in ("[:bad:]", "[:alpha:]", "[", "a", r"\x42", r"\102"):
            for start in ("0", r"\0"):
                patterns.append("[" + start + "-" + escape + "-" + suffix + "]")
            patterns.append("[" + escape + "-" + suffix + "]")
    patterns += ["(" * n + "a" + ")" * n for n in (1, 10, 100, 500)]
    patterns += ["(" + "a" * n + "){1000}" for n in (1, 100, 500, 1000)]
    request = tmp_path / "patterns.json"
    request.write_text(json.dumps(patterns), encoding="utf-8")
    executable = tmp_path / ("oracle.exe" if os.name == "nt" else "oracle")
    subprocess.run(["go", "test", "-c", "-o", str(executable), "./internal/artifact"],
                   cwd=ROOT, check=True, capture_output=True, timeout=120)
    subprocess.run([str(executable), "-test.run=^TestRegexDifferentialOracle$"],
                   cwd=ROOT / "internal/artifact", check=True, capture_output=True,
                   env={**os.environ, "AGENTSUITE_REGEX_ORACLE": str(request)}, timeout=120)
    expected = json.loads(Path(str(request) + ".result").read_bytes())
    mismatches = [(pattern, want, valid(pattern))
                  for pattern, want in zip(patterns, expected) if valid(pattern) != want]
    assert len(expected) == len(patterns)
    assert not mismatches, mismatches[:20]


def test_native_regex_parse_certificate(monkeypatch):
    from agent_suite._regex import valid

    native = re2._re2.RE2

    def exhausted(pattern, options):
        options.max_mem = 1024
        return native(pattern, options)

    monkeypatch.setattr(re2._re2, "RE2", exhausted)
    assert valid("(abc){1000}")
    # Even a program that cannot fit must finish parsing its malformed tail.
    prefix = "a{0,1000}" * 113
    for suffix in ("(", "[", chr(92), "{2,1}", "(?i){2}"):
        assert not valid(prefix + suffix), suffix
    assert not valid("(a{100}){11}")
    assert not valid("((a{1001}){0}){1000}")
    assert valid("((a{1000}){0}){1000}")
    # Authored text in a parse diagnostic is not a compiler resource status.
    for invalid in ("(pattern too large", "pattern too large)",
                    "(pattern too large - compile failed"):
        assert not valid(invalid), invalid

    class UnknownFailure:
        def ok(self):
            return False

        def error(self):
            return b"pattern too large - unknown failure"

    monkeypatch.setattr(re2._re2, "RE2", lambda pattern, options: UnknownFailure())
    with pytest.raises(RuntimeError, match="native regex compiler resource failure"):
        valid("a")

    def allocation_failed(pattern, options):
        raise MemoryError("native allocation failed")

    monkeypatch.setattr(re2._re2, "RE2", allocation_failed)
    with pytest.raises(MemoryError, match="native allocation failed"):
        valid("[a-z]")
