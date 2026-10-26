"""Equality-preserving JSON uniqueness; non-JSON Python values keep stock behavior."""
from __future__ import annotations

import math
from collections.abc import Hashable, Iterator
from typing import Any

from jsonschema import Draft202012Validator, ValidationError, validators

from ._json import Number

_stock_unique = Draft202012Validator.VALIDATORS['uniqueItems']


def _key(value: Any) -> Hashable:
    kind = type(value)
    if value is None:
        return ('null',)
    if kind is bool:
        return ('boolean', value)
    if kind in (int, float, Number):
        if isinstance(value, float) and not math.isfinite(value):
            raise TypeError('non-finite number')
        # Number inherits float equality/hash: lexemes do not affect JSON equality.
        return ('number', value)
    if kind is str:
        return ('string', value)
    if kind is list:
        return ('array', tuple(_key(child) for child in value))
    if kind is dict and all(type(key) is str for key in value):
        return ('object', frozenset((key, _key(child)) for key, child in value.items()))
    raise TypeError('not a plain JSON value')


def _unique_items(validator: Any, unique: bool, instance: Any, schema: Any) -> Iterator[ValidationError]:
    if not unique or not validator.is_type(instance, 'array'):
        return
    if type(instance) is not list:
        yield from _stock_unique(validator, unique, instance, schema)
        return
    try:
        # Inspect every value before deciding: a later non-JSON value must send
        # the WHOLE array through the original equality/sorting behavior.
        keys = [_key(value) for value in instance]
    except TypeError:
        yield from _stock_unique(validator, unique, instance, schema)
        return
    if len(set(keys)) != len(keys):
        yield ValidationError(f'{instance!r} has non-unique elements')


Validator = validators.extend(Draft202012Validator, {'uniqueItems': _unique_items})
