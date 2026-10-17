// Copyright (c) Microsoft Corporation. Licensed under the MIT License.
export const v1 = paths => ({
  version: 'agentsuite.policy/v1', denyWritePaths: paths,
  requiredCapabilities: ['filesystem/deny-write/v1'],
});
export const endpoint = (port = 443, address = '192.0.2.10') => ({ address, protocol: 'TCP', port });
export const v2 = endpoints => ({
  version: 'agentsuite.policy/v2', network: { egressAllow: endpoints },
  requiredCapabilities: ['network/egress-allow/v1'],
});
export const encode = value => new TextEncoder().encode(typeof value === 'string' ? value : JSON.stringify(value));

// Explicit expectations prevent a differential suite from accepting shared mistakes.
export function cases() {
  const out = [];
  const add = (name, value, accepted) => out.push({ name, data: encode(value), accepted });
  add('filesystem', v1(['/b', '/a', '/a', '/𐀀', '/\ue000']), true);
  add('network', v2([endpoint(), endpoint(80, '10.0.0.2'), endpoint()]), true);
  add('deny-all', v2([]), true);
  for (const path of ['/x', '/a\\b', '/a\nb', '/a\tb', '/a\rb', '/a\bb', '/a\fb', '/a\u0001b', '/a"b', '/<>&', '/\u2028\u2029', '/é', '/é', '/�']) {
    add(`valid path ${JSON.stringify(path)}`, v1([path]), true);
  }
  for (const path of ['', '/', 'relative', '//a', '/a/', '/a//b', '/a/./b', '/a/../b', '/a/.', '/a/..', '/a\0b']) {
    add(`invalid path ${JSON.stringify(path)}`, v1([path]), false);
  }
  for (const value of [null, [], true, 1, {}, { version: null }, { version: 'agentsuite.policy/v3' }]) add('root/version shape', value, false);
  for (const field of ['denyWritePaths', 'requiredCapabilities']) {
    for (const value of [undefined, null, [], {}, '', [null], [1], [true]]) {
      add(`v1 ${field} shape ${JSON.stringify(value)}`, { ...v1(['/x']), [field]: value }, false);
    }
  }
  for (const value of [undefined, null, [], {}, '', [null], ['unknown'], ['network/egress-allow/v1', 'network/egress-allow/v1']]) {
    add('v2 capabilities', { ...v2([]), requiredCapabilities: value }, false);
  }
  for (const field of ['network', 'Network', 'Version', 'unknown', '__proto__']) {
    add('v1 closed fields', { ...v1(['/x']), [field]: null }, false);
  }
  for (const value of [null, [], {}]) add('v2 filesystem forbidden', { ...v2([]), denyWritePaths: value }, false);
  for (const value of [undefined, null, [], '', 1, { egressAllow: null }, {}, { egressAllow: [], unknown: null }]) {
    add('network shape', { ...v2([]), network: value }, false);
  }
  for (const value of [null, {}, [], '', { ...endpoint(), Port: 80 }, { ...endpoint(), other: false }]) add('endpoint shape', v2([value]), false);
  for (const field of ['address', 'protocol', 'port']) {
    for (const value of [undefined, null, [], {}, false]) add(`endpoint ${field}`, v2([{ ...endpoint(), [field]: value }]), false);
  }
  for (const address of ['0.0.0.0', '255.255.255.255', '127.0.0.1']) add('IPv4 allowed syntax', v2([endpoint(1, address)]), true);
  for (const address of ['01.2.3.4', '256.0.0.1', '1.2.3', '1.2.3.4.', '1.2.3.4/32', '::1', '::ffff:1.2.3.4', 'example.invalid', ' 1.2.3.4', '+1.2.3.4', '1.2.3.٤']) {
    add('IPv4 rejection', v2([endpoint(80, address)]), false);
  }
  for (const protocol of ['tcp', 'UDP', '', 'TCP\0']) add('protocol', v2([{ ...endpoint(), protocol }]), false);
  const networkText = JSON.stringify(v2([endpoint()]));
  for (const [number, valid] of [
    ['1', true], ['65535', true], ['443.0', true], ['4.43e2', true], ['44300e-2', true],
    ['0.443e3', true], ['1.00000000000000000000000000000', true], ['1e+0000', true],
    ['-0', false], ['0', false], ['65536', false], ['-1', false], ['1.1', false],
    ['443.00000000000000000001', false], ['65535.0000000000000001', false],
    ['0.999999999999999999999', false], ['1.0000000000000001', false],
    ['9007199254740993', false], ['9223372036854775807', false], ['1e309', false],
    ['1e-999999999', false], ['1e999999999', false], ['01', false], ['+1', false],
    ['.1', false], ['1.', false], ['NaN', false], ['Infinity', false], ['"443"', false],
  ]) add(`numeric lexeme ${number}`, networkText.replace('443', number), valid);
  // Long coefficients exercise exact decimal checks without huge BigInt allocations.
  for (const zeros of [1000, 100_000]) {
    add(`integral long decimal ${zeros}`, networkText.replace('443', '443.' + '0'.repeat(zeros)), true);
    add(`fraction rounds to integer ${zeros}`, networkText.replace('443', '443.' + '0'.repeat(zeros) + '1'), false);
  }
  // big.Rat's exponent guard is observable even when Float64 cancels to one.
  add('Go rational exponent guard', networkText.replace('443', '1' + '0'.repeat(1_000_001) + 'e-1000001'), false);
  const filesystemText = JSON.stringify(v1(['/x']));
  for (const text of [
    filesystemText.slice(0, -1) + ',"version":"agentsuite.policy/v1"}',
    filesystemText.replace('"version"', '"Version"'),
    filesystemText.slice(0, -1) + ',"ver\\u0073ion":"agentsuite.policy/v1"}',
    networkText.replace('"port":443', '"port":443,"p\\u006frt":443'),
    networkText.replace('"egressAllow":', '"egressAllow":[],"egressAllow":'),
    filesystemText + '{}', filesystemText + 'false', filesystemText + 'x',
    '\ufeff' + filesystemText, filesystemText.replace('/x', '/\\ud800'),
    filesystemText.replace('/x', '/\\udc00'), filesystemText.replace('/x', '/\\ud800\\u0041'),
    filesystemText.replace('/x', '/\n'), filesystemText.replace('/x', '/\\q'),
    filesystemText.replace('/x', '/\\u0000'), filesystemText.replace('"/x"', '"/x",'),
  ]) add('strict JSON', text, false);
  add('escaped valid pair', filesystemText.replace('/x', '/\\ud800\\udc00'), true);
  add('escaped slash', filesystemText.replace('/x', '\\/x'), true);
  add('escaped backslash not surrogate', filesystemText.replace('/x', '/\\\\ud800'), true);
  add('whitespace', ' \r\n\t' + filesystemText + '\r\n ', true);
  for (const count of [4096, 4097]) {
    add(`path count ${count}`, v1(Array(count).fill('/x')), count === 4096);
    add(`endpoint count ${count}`, v2(Array(count).fill(endpoint())), count === 4096);
  }
  // Byte size, not JS string length; exercise the exact limit including framing.
  const overhead = encode(v1(['/'])).length;
  for (const size of [(4 << 20) - 1, 4 << 20, (4 << 20) + 1]) {
    add(`byte limit ${size}`, v1(['/' + 'x'.repeat(size - overhead)]), size <= (4 << 20));
  }
  for (const depth of [99, 100, 101]) add(`nesting ${depth}`, '{"x":' + '['.repeat(depth) + '0' + ']'.repeat(depth) + '}', false);
  add('object member bound', '{' + Array.from({ length: 1025 }, (_, i) => `"k${i}":0`).join(',') + '}', false);
  for (let control = 1; control < 32; control++) {
    add(`escaped control ${control}`, v1(['/a' + String.fromCharCode(control) + 'b']), true);
  }
  add('unicode escaped root keys', filesystemText.replace('version', 'ver\\u0073ion'), true);
  const unicodePath = v1(['/é']);
  add('multibyte byte count', unicodePath, true);
  add('deep unknown object members', '{"unknown":' + '['.repeat(100) + '{}' + ']'.repeat(100) + '}', false);
  add('document member bound', '{"unknown":[' + Array(100_001).fill('{"k":0}').join(',') + ']}', false);
  for (const bytes of [[0xff], [0xc0, 0xaf], [0xed, 0xa0, 0x80], [0xef, 0xbb, 0xbf]]) {
    const prefix = encode(filesystemText.replace('/x', '/PLACEHOLDER'));
    const marker = Buffer.from(prefix).indexOf('PLACEHOLDER');
    out.push({ name: 'invalid UTF-8/BOM-in-string', data: Buffer.concat([prefix.slice(0, marker), Buffer.from(bytes), prefix.slice(marker + 11)]), accepted: bytes[0] === 0xef });
  }
  return out;
}

// Bounded, seeded mutations, no fuzzing service or non-reproducible randomness.
export function generatedCases() {
  let seed = 0x12c0ffee;
  const next = n => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed % n; };
  const result = [];
  for (let i = 0; i < 240; i++) {
    const endpoints = Array.from({ length: next(6) }, () => endpoint(1 + next(65535), `${next(256)}.${next(256)}.${next(256)}.${next(256)}`));
    const paths = Array.from({ length: 1 + next(6) }, () => ['/a', '/b', '/𐀀', '/\ue000', '/x\n', '/é'][next(6)]);
    const data = encode(i % 2 ? v1(paths) : v2(endpoints));
    result.push({ name: `seeded-valid-${i}`, data, accepted: true });
    const number = 1 + next(65535);
    const numberText = JSON.stringify(v2([endpoint(number)]));
    const zeroCount = 1 + next(24);
    result.push({ name: `seeded-decimal-${i}`, data: encode(numberText.replace(`\"port\":${number}`, `\"port\":${number}.${'0'.repeat(zeroCount)}`)), accepted: true });
    result.push({ name: `seeded-exponent-${i}`, data: encode(numberText.replace(`\"port\":${number}`, `\"port\":${number}00e-2`)), accepted: true });
    result.push({ name: `seeded-fraction-${i}`, data: encode(numberText.replace(`\"port\":${number}`, `\"port\":${number}.${'0'.repeat(zeroCount)}1`)), accepted: false });
    if (i % 3 === 0) {
      const mutated = data.slice();
      mutated[next(mutated.length)] = next(256);
      result.push({ name: `seeded-mutation-${i}`, data: mutated });
    }
  }
  return result;
}
