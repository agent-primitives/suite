// Copyright (c) Microsoft Corporation. Licensed under the MIT License.
// A bounded JSON reader for policy wire inputs, not a general JCS implementation.
// Keep number lexemes until the port check; JSON.parse would round fractions.
export class NumberToken {
  constructor(readonly text: string) {}
}
export type Value = null | boolean | string | NumberToken | Value[] | ObjectValue;
export interface ObjectValue { [key: string]: Value }
export const maxBytes = 4 << 20;
export const encoder = new TextEncoder();
export function refuse(message: string): never {
  throw new Error(message);
}

function unicode(value: string): string {
  for (let i = 0; i < value.length; i++) {
    const unit = value.charCodeAt(i);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const low = value.charCodeAt(++i);
      if (!(low >= 0xdc00 && low <= 0xdfff)) refuse('Unpaired surrogate');
    } else if (unit >= 0xdc00 && unit <= 0xdfff) refuse('Unpaired surrogate');
  }
  return value;
}

export function readJSON(data: Uint8Array): Value {
  if (data.length === 0 || data.length > maxBytes) refuse('JSON byte limit');
  // Preserve BOM: Go rejects it rather than treating it as whitespace.
  const text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(data);
  let pos = 0;
  let members = 0;
  function space(): void {
    while (/[\x20\t\r\n]/.test(text[pos] ?? '') && pos < text.length) pos++;
  }
  function string(): string {
    const start = pos++;
    while (pos < text.length) {
      const char = text[pos++];
      if (char === '"') return unicode(JSON.parse(text.slice(start, pos)) as string);
      if (char === '\\') pos++; // JSON.parse checks escape syntax and controls.
    }
    return refuse('Unterminated string');
  }
  function value(depth: number): Value {
    space();
    const char = text[pos];
    if (char === '"') return string();
    if (char === '{' || char === '[') {
      if (depth >= 100) refuse('JSON nesting limit');
      pos++;
      space();
      if (char === '[') {
        const result: Value[] = [];
        if (text[pos] === ']') { pos++; return result; }
        while (true) {
          result.push(value(depth + 1));
          space();
          if (text[pos] === ']') { pos++; return result; }
          if (text[pos++] !== ',') refuse('Expected array separator');
        }
      }
      const result: ObjectValue = Object.create(null) as ObjectValue;
      let count = 0;
      if (text[pos] === '}') { pos++; return result; }
      while (true) {
        if (++count > 1024 || ++members > 100_000) refuse('JSON member limit');
        space();
        if (text[pos] !== '"') refuse('Expected object key');
        const key = string();
        if (Object.hasOwn(result, key)) refuse('Duplicate JSON key');
        space();
        if (text[pos++] !== ':') refuse('Expected colon');
        result[key] = value(depth + 1);
        space();
        if (text[pos] === '}') { pos++; return result; }
        if (text[pos++] !== ',') refuse('Expected object separator');
      }
    }
    for (const [word, literal] of [['true', true], ['false', false], ['null', null]] as const) {
      if (text.startsWith(word, pos)) { pos += word.length; return literal; }
    }
    const match = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(text.slice(pos));
    if (!match || !Number.isFinite(Number(match[0]))) return refuse('Invalid JSON value');
    pos += match[0].length;
    return new NumberToken(match[0]);
  }
  const result = value(0);
  space();
  if (pos !== text.length) refuse('Trailing JSON data');
  return result;
}

export function object(value: Value | undefined, fields: readonly string[]): ObjectValue {
  if (!value || typeof value !== 'object' || Array.isArray(value) || value instanceof NumberToken) {
    return refuse('Expected object');
  }
  if (Object.keys(value).some(key => !fields.includes(key))) refuse('Unknown field');
  return value;
}
export function list(value: Value | undefined): Value[] {
  if (!Array.isArray(value)) return refuse('Expected non-null list');
  return value;
}
export function stringValue(value: Value | undefined): string {
  if (typeof value !== 'string') return refuse('Expected string');
  return value;
}

export function port(value: Value | undefined): number {
  if (!(value instanceof NumberToken)) return refuse('Expected numeric port');
  const approximate = Number(value.text);
  if (approximate < 1 || approximate > 65535) refuse('Port out of range');
  const [mantissa = '', exponent = '0'] = value.text.toLowerCase().split('e');
  const fraction = mantissa.split('.')[1]?.length ?? 0;
  // Go big.Rat bounds the decimal exponent after accounting for the radix point.
  const shift = Number(exponent) - fraction;
  if (!Number.isSafeInteger(shift) || Math.abs(shift) > 1_000_000) refuse('Port exponent limit');
  let digits = mantissa.replace('.', '').replace(/^0+/, '');
  if (shift < 0) {
    const places = -shift;
    if (places >= digits.length || !/^0*$/.test(digits.slice(-places))) refuse('Fractional port');
    digits = digits.slice(0, -places);
  } else {
    if (digits.length + shift > 5) refuse('Port out of range');
    digits += '0'.repeat(shift);
  }
  const exact = Number(digits);
  if (!Number.isInteger(exact) || exact < 1 || exact > 65535) refuse('Port out of range');
  return exact;
}
