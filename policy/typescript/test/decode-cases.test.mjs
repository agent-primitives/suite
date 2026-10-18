// Copyright (c) Microsoft Corporation. Licensed under the MIT License.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { canonicalize, decodePolicy, digest, verifyPayload } from '../dist/index.js';

test('shared decode corpus: acceptance, canonical bytes, digest and payload', async t => {
  const corpus = await readFile(new URL('../../testdata/decode-cases.jsonl', import.meta.url), 'utf8');
  assert.ok(corpus.endsWith('\n'), 'decode-cases.jsonl must end with a newline');
  const lines = corpus.slice(0, -1).split('\n');
  assert.ok(lines.length >= 150, `decode-cases.jsonl has ${lines.length} cases, want at least 150`);
  const encode = value => new TextEncoder().encode(value);
  for (const line of lines) {
    const entry = JSON.parse(line);
    await t.test(entry.name, async () => {
      assert.notEqual(entry.input !== undefined, entry.inputHex !== undefined,
        'exactly one of input and inputHex is required');
      if (entry.inputHex !== undefined) {
        assert.match(entry.inputHex, /^(?:[0-9a-fA-F]{2})*$/, 'inputHex must encode whole bytes');
      }
      const input = entry.inputHex === undefined ? encode(entry.input)
        : new Uint8Array(Buffer.from(entry.inputHex, 'hex'));
      if (!entry.valid) {
        assert.throws(() => decodePolicy(input));
        return;
      }
      const policy = decodePolicy(input);
      const canonical = canonicalize(input);
      assert.deepEqual(canonical, encode(entry.canonical));
      assert.equal(await digest(canonical), entry.digest);
      await verifyPayload({ version: policy.version, requiredCapabilities: policy.requiredCapabilities,
        policyBytes: canonical, policyDigest: entry.digest });
    });
  }
});
