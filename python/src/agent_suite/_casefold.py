"""Go x/text folding compatibility, independent of Python Unicode versions."""

# Absolute reference mappings, not interpreter-version switches. Cherokee's Go
# transform and Unicode 14/16 additions differ from Python's native casefold.
_RANGES = (
    (0x13A0, 0x13EF, 0x97D0),
    (0x13F0, 0x13F5, 8),
    (0x10570, 0x1057A, 0x27),
    (0x1057C, 0x1058A, 0x27),
    (0x1058C, 0x10592, 0x27),
    (0x10594, 0x10595, 0x27),
    (0x10D50, 0x10D65, 0),
)
_OVERRIDES = {
    0x1C89: "\u1c89",
    0x2C2F: "\u2c5f",
    0xA7C0: "\ua7c1",
    0xA7CB: "\ua7cb",
    0xA7CC: "\ua7cc",
    0xA7D0: "\ua7d1",
    0xA7D6: "\ua7d7",
    0xA7D8: "\ua7d9",
    0xA7DA: "\ua7da",
    0xA7DC: "\ua7dc",
}


def _rune(value: str) -> str:
    number = ord(value)
    for first, last, offset in _RANGES:
        if first <= number <= last:
            return chr(number + offset)
    return _OVERRIDES.get(number, value.casefold())


def fold_case(value: str) -> str:
    return "".join(_rune(char) for char in value)
