"""Go 1.26 regexp.Compile acceptance; never used to match authored patterns.

The caller owns nonblank/1024-UTF-8-byte validation. Private binding API use is
intentional and covered by the exact google-re2 pin and differential tests.
"""

import re2

# Unicode 15.0 names from Go 1.26 unicode/{Categories,CategoryAliases,Scripts},
# normalized as regexp/syntax.canonicalName. Only already-canonical Scripts keys
# are reachable in that Go version (e.g. Old_Italic and SignWriting are not).
# Immutable vocabulary, not a compiler cache; no Unicode rune tables are needed.
_PROPERTIES = frozenset("""
adlam ahom any arabic armenian ascii assigned avestan balinese bamum batak bengali
bhaiksuki bopomofo brahmi braille buginese buhid c carian casedletter cc cf chakma cham
cherokee chorasmian closepunctuation cn cntrl co combiningmark common
connectorpunctuation control coptic cs cuneiform currencysymbol cypriot cyrillic
dashpunctuation decimalnumber deseret devanagari digit dogra duployan elbasan elymaic
enclosingmark ethiopic finalpunctuation format georgian glagolitic gothic grantha greek
gujarati gurmukhi han hangul hanunoo hatran hebrew hiragana inherited initialpunctuation
javanese kaithi kannada katakana kawi kharoshthi khmer khojki khudawadi l lao latin lc
lepcha letter letternumber limbu lineseparator lisu ll lm lo lowercaseletter lt lu lycian
lydian m mahajani makasar malayalam mandaic manichaean marchen mark mathsymbol mc me
medefaidrin miao mn modi modifierletter modifiersymbol mongolian mro multani myanmar n
nabataean nandinagari nd newa nko nl no nonspacingmark number nushu ogham openpunctuation
oriya osage osmanya other otherletter othernumber otherpunctuation othersymbol p
palmyrene paragraphseparator pc pd pe pf phoenician pi po privateuse ps punct punctuation
rejang runic s samaritan saurashtra sc separator sharada shavian siddham sinhala sk sm so
sogdian soyombo spaceseparator spacingmark sundanese surrogate symbol syriac tagalog
tagbanwa takri tamil tangsa tangut telugu thaana thai tibetan tifinagh tirhuta
titlecaseletter toto ugaritic unassigned uppercaseletter vai vithkuqi wancho yezidi yi z
zl zp zs
""".split())


def valid(pattern: str) -> bool:
    """Check syntax with native RE2 after adapting the proven Go differences."""
    out: list[str] = []
    i = 0
    in_class = False
    first = False
    class_start = 0
    class_scalar = False
    range_end = False
    groups: list[int] = []
    while i < len(pattern):
        c = pattern[i]
        if c == "\\":
            escape = pattern[i:i + 2]
            if escape == r"\Q" and not in_class:
                end = pattern.find(r"\E", i + 2)
                end = len(pattern) if end < 0 else end
                # Quoted text is literal, including otherwise-invalid syntax.
                # Keep one atom per rune so a following repeat binds identically.
                out.append("a" * (end - i - 2))
                i = min(end + 2, len(pattern))
                continue
            if escape == r"\C":
                return False
            if escape in (r"\p", r"\P"):
                end = i + 3
                name = pattern[i + 2:end]
                if name == "{":
                    close = pattern.find("}", end)
                    if close < 0:
                        return False
                    name = pattern[end:close]
                    end = close + 1
                if name.startswith("^"):
                    name = name[1:]
                # Go canonicalName changes ASCII only, not Unicode case folds.
                canonical = name.replace("_", "").replace("-", "").replace(" ", "").lower()
                if not name.isascii() or canonical not in _PROPERTIES:
                    return False
                # Inside a class retain a class-valued atom: replacing it with
                # a literal could hide an invalid range endpoint such as a-\pL.
                out.append(r"\p{Any}" if in_class else "a")
                i = end
            elif not in_class and escape in (r"\d", r"\D", r"\s", r"\S", r"\w", r"\W"):
                out.append("a")
                i += 2
            elif escape == r"\x" or (len(escape) == 2 and escape[1] in "01234567"):
                end = i + 2
                if escape == r"\x":
                    if pattern[end:end + 1] == "{":
                        close = pattern.find("}", end + 1)
                        if close < 0:
                            return False
                        end = close + 1
                    else:
                        end = min(end + 2, len(pattern))
                else:
                    while end < min(i + 4, len(pattern)) and pattern[end] in "01234567":
                        end += 1
                # Consume one whole escaped rune before updating range state.
                # Classes retain its spelling for native endpoint validation.
                if not _native_valid(pattern[i:end]):
                    return False
                out.append(pattern[i:end] if in_class else "a")
                i = end
            else:
                out.append(escape)
                i += len(escape)
            if in_class:
                class_scalar = not range_end and escape not in (
                    r"\p", r"\P", r"\d", r"\D", r"\s", r"\S", r"\w", r"\W")
                range_end = False
            first = False
            continue
        if not in_class and c == "{":
            end = pattern.find("}", i + 1)
            counts = pattern[i + 1:end].split(",") if end >= 0 else []
            # Native integer overflow makes huge repeats literal; Go rejects
            # them. Only canonical ASCII counts are repeats in Go; malformed
            # braces/leading zeros stay literal. Do not rewrite any counts.
            if len(counts) in (1, 2) and counts[0] and all(
                n.isascii() and n.isdecimal() and (len(n) == 1 or n[0] != "0")
                for n in counts if n
            ):
                if any(len(n) > 4 or int(n) > 1000 for n in counts if n):
                    return False
        if not in_class and (pattern.startswith("(?P<", i) or pattern.startswith("(?<", i)):
            start = i + (4 if pattern.startswith("(?P<", i) else 3)
            end = pattern.find(">", start)
            if end < 0:
                return False
            name = pattern[start:end]
            if not name or not all("a" <= x <= "z" or "A" <= x <= "Z" or
                                   "0" <= x <= "9" or x == "_" for x in name):
                return False
            groups.append(len(out))
            out.append(pattern[i:end + 1])
            i = end + 1
            continue
        if c == "[" and not in_class:
            class_start = len(out)
            class_scalar = range_end = False
            in_class = True
            first = True
            out.append(c)
            i += 1
            if pattern[i:i + 1] == "^":
                out.append("^")
                i += 1
            continue
        # Go consumes a range endpoint as one rune, not a POSIX atom. Make
        # that literal "[" explicit for native parsing and class termination.
        if in_class and range_end and c == "[":
            out.append(r"\[")
            class_scalar = range_end = first = False
            i += 1
            continue
        if in_class and pattern.startswith("[:", i):
            end = pattern.find(":]", i + 2)
            if end >= 0:
                out.append(pattern[i:end + 2])
                i = end + 2
                first = False
                class_scalar = False
                continue
        if not in_class and c == "(":
            groups.append(len(out))
            # Preserve flag letters while reducing ordinary folded literals.
            if pattern.startswith("(?", i):
                end = i + 2
                while end < len(pattern) and pattern[end] in "imsU-":
                    end += 1
                out.append(pattern[i:end])
                i = end
                continue
        if not in_class and c == ")" and groups:
            start = groups.pop()
            zero = pattern.startswith("{0}", i + 1) or pattern.startswith("{0,0}", i + 1)
            if zero:
                atom = "".join(out[start:]) + ")"
                # Go repeatIsValid stops at a zero-count subtree; C++ keeps
                # multiplying its inner counts. Validate it before erasing it,
                # so even dead branches must retain valid syntax/counts.
                if not _native_valid(atom):
                    return False
                # Bare (?flags) is not an atom. Leave it for the native parser.
                header = atom[2:-1] if atom.startswith("(?") else ":"
                if any(x not in "imsU-" for x in header):
                    out[start:] = ["(?:"]
        if in_class and c == "]" and not first:
            # A complete class is checked exactly once without its outer repeat.
            # Preserve first ']', POSIX atoms, escape and range syntax until now.
            if not _native_valid("".join(out[class_start:]) + "]"):
                return False
            out[class_start:] = ["a"]
            in_class = False
            i += 1
            continue
        if in_class:
            if c == "-" and class_scalar and pattern[i + 1:i + 2] != "]":
                range_end, class_scalar = True, False
            else:
                class_scalar, range_end = not range_end, False
        first = False
        # Dot, UTF-8 literals and ASCII's Unicode-folding K/S do not affect
        # syntax, but their byte-range programs can explode under repetition.
        out.append("a" if not in_class and (c == "." or not c.isascii() or c in "kKsS") else c)
        i += 1

    # An unfinished class must not be mistaken for a reduced literal.
    return not in_class and _native_valid("".join(out))


def _native_valid(pattern: str) -> bool:
    options = re2.Options()
    options.log_errors = False
    options.encoding = re2.Options.Encoding.UTF8
    # Syntax only: bound program construction, not accepted expression size.
    # Pinned RE2::Init parses the ENTIRE expression before CompileToProg;
    # this exact failure certifies successful parsing, before IsOnePass work.
    # https://github.com/google/re2/blob/2025-11-05/re2/re2.cc#L235-L283
    options.max_mem = 64 << 10
    compiled = re2._re2.RE2(pattern.encode("utf-8"), options)
    if compiled.ok():
        return True
    error = compiled.error()
    if error == b"pattern too large - compile failed":
        return True
    if error.startswith(b"pattern too large"):
        # Resource/binding failure is not an invalid user expression.
        raise RuntimeError(f"native regex compiler resource failure: {error!r}")
    return False
