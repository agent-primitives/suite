#!/usr/bin/env python3
"""Offline local Markdown link/heading check, adapted from kaimahi's checker.

Usage: python3 scripts/check-doc-links.py [file.md ... | --selftest]
No arguments scans Git-tracked and non-ignored untracked Markdown, including
hidden directories. External URLs are not fetched. Supports inline/image,
reference-definition and HTML href/src links, excluding fenced/inline code.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit


FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
LINK = re.compile(r'(?<!\\)\[[^\]]*\]\((<[^>]+>|[^)\s]+)(?:\s+"[^"]*")?\)')
HTML = re.compile(r'<(?:img|a)\b[^>]*?\b(?:src|href)\s*=\s*[\"\']([^\"\']*)[\"\']',
                  re.IGNORECASE | re.DOTALL)
REF_DEF = re.compile(r"^ {0,3}\[([^\]]+)\]:[ \t]*<?([^>\s]+)>?", re.MULTILINE)
REF_USE = re.compile(r"(?<!\\)\[([^\]]*)\]\[([^\]]*)\]")


def prose(path, inline_code=False):
    lines, fence = [], ""
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        match = FENCE.match(line)
        if match and (not fence or (match[1][0] == fence[0] and len(match[1]) >= len(fence))):
            fence = "" if fence else match[1]
            lines.append("\n")
        elif fence:
            lines.append("\n")
        else:
            lines.append(line if inline_code else re.sub(r"`[^`\n]*`", lambda m: " " * len(m[0]), line))
    return "".join(lines)


def slugs(path):
    seen, anchors = {}, set()
    for match in re.finditer(r"^#{1,6}\s+(.*?)\s*#*\s*$", prose(path, inline_code=True), re.MULTILINE):
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", match[1])
        text = re.sub(r"[`*_]", "", text).strip().lower()
        slug = re.sub(r"[^\w\- ]", "", text).replace(" ", "-")
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def label(text):
    return " ".join(text.split()).lower()


def check(path, cache):
    problems = []
    try:
        text = prose(path)
    except (OSError, UnicodeError) as error:
        return [f"{path}: cannot read Markdown: {error}"]

    def verify(target, position):
        target = target.removeprefix("<").removesuffix(">")
        url = urlsplit(target)
        if url.scheme or url.netloc:
            return
        resolved = path.parent / unquote(url.path) if url.path else path
        line = text.count("\n", 0, position) + 1
        if not resolved.exists():
            problems.append(f"{path}:{line}: missing target {target}")
        elif url.fragment and resolved.suffix.lower() == ".md":
            if resolved not in cache:
                cache[resolved] = slugs(resolved)
            if unquote(url.fragment) not in cache[resolved]:
                problems.append(f"{path}:{line}: no heading for {target}")

    for pattern in (LINK, HTML):
        for match in pattern.finditer(text):
            verify(match[1], match.start())
    definitions = {label(m[1]): m for m in REF_DEF.finditer(text)}
    for match in definitions.values():
        verify(match[2], match.start())
    if definitions:
        for match in REF_USE.finditer(text):
            name = label(match[2] or match[1])
            if name not in definitions:
                line = text.count("\n", 0, match.start()) + 1
                problems.append(f"{path}:{line}: no reference definition for [{name}]")
    return problems


def markdown_files():
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=True, capture_output=True, text=True,
    )
    return sorted({name for name in result.stdout.split("\0") if name.endswith(".md")})


def main(argv):
    if argv == ["--selftest"]:
        return selftest()
    files = argv or markdown_files()
    if not files:
        print("check-doc-links: no Markdown files to scan", file=sys.stderr)
        return 1
    problems, cache = [], {}
    for name in files:
        problems.extend(check(Path(name), cache))
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"check-doc-links: {len(files)} files, {len(problems)} problems")
    return int(bool(problems))


def selftest():
    class LinkTests(unittest.TestCase):
        def test_links_and_anchors(self):
            # Each bad fixture names a break that an always-green checker misses.
            cases = [
                ("file", "[x](there.md)", 0),
                ("missing file", "[x](gone.md)", 1),
                ("anchor", "[x](there.md#a-real-heading)", 0),
                ("missing anchor", "[x](there.md#gone)", 1),
                ("duplicate heading", "[x](there.md#a-real-heading-1)", 0),
                ("code heading", "[x](there.md#example)", 1),
                ("same document", "# Here\n[x](#here)", 0),
                ("missing same-document anchor", "# Here\n[x](#gone)", 1),
                ("image", "![x](pic.png)", 0),
                ("missing image", "![x](gone.png)", 1),
                ("HTML link", '<a href="there.md#a-real-heading">x</a>', 0),
                ("missing HTML link", '<a href="gone.md">x</a>', 1),
                ("multiline HTML image", '<img\n src="pic.png">', 0),
                ("missing HTML image", '<img\n src="gone.png">', 1),
                ("reference", "[x][t]\n[t]: there.md#a-real-heading", 0),
                ("missing reference target", "[x][t]\n[t]: gone.md", 1),
                ("missing reference definition", "[x][t]\n[other]: there.md", 1),
                ("collapsed reference", "[T][]\n[t]: there.md", 0),
                ("shortcut reference", "[t]\n[t]: gone.md", 1),
                ("code span", "`[x](gone.md)`", 0),
                ("fenced code", "```md\n[x](gone.md)\n```", 0),
                ("tilde code", "~~~\n[x](gone.md)\n~~~", 0),
                ("external URLs", "[x](https://example.invalid/no#heading)\n"
                 "[email](mailto:nobody@example.invalid)", 0),
                ("angle destination", "[x](<there.md#a-real-heading>)", 0),
                ("encoded path", "[x](with%20space.md)", 0),
                ("encoded missing path", "[x](gone%20space.md)", 1),
                ("relative parent", "[x](../there.md#a-real-heading)", 0),
                ("directory", "[x](../)", 0),
            ]
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "there.md").write_text(
                    "# There\n## A Real Heading\n## A Real Heading\n"
                    "```\n## Example\n```\n", encoding="utf-8")
                (root / "pic.png").write_bytes(b"image")
                (root / "with space.md").write_text("# Space\n", encoding="utf-8")
                (root / "nested").mkdir()
                # Links are normally siblings; parent/directory cases use nested/.
                for title, body, wanted in cases:
                    with self.subTest(title=title):
                        parent = root / "nested" if title in {"relative parent", "directory"} else root
                        path = parent / "a.md"
                        path.write_text(body, encoding="utf-8")
                        self.assertEqual(int(bool(check(path, {}))), wanted)

        def test_cli_discovery_and_failures(self):
            script = str(Path(__file__).resolve())
            with tempfile.TemporaryDirectory() as tmp:
                subprocess.run(["git", "init", "-q", tmp], check=True, capture_output=True)
                def run(*args):
                    return subprocess.run([sys.executable, script, *args], cwd=tmp,
                                          capture_output=True, text=True)
                self.assertEqual(run().returncode, 1)  # Empty scans must not pass.
                root = Path(tmp)
                (root / "a.md").write_text("# Here\n[x](#here)\n", encoding="utf-8")
                self.assertEqual(run().returncode, 0)
                (root / ".github").mkdir()
                (root / ".github" / "review.md").write_text("[x](gone.md)", encoding="utf-8")
                self.assertEqual(run().returncode, 1)  # Hidden docs are included.
                self.assertEqual(run("missing.md").returncode, 1)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LinkTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
