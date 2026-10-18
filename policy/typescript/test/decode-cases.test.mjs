// Copyright (c) Microsoft Corporation. Licensed under the MIT License.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { canonicalize, decodePolicy, digest, verifyPayload } from '../dist/index.js';

const corpusURL = new URL('../../testdata/decode-cases.jsonl', import.meta.url);

function casesFromCorpus(corpus) {
  assert.ok(corpus.endsWith('\n'), 'decode-cases.jsonl must end with a newline');
  const lines = corpus.slice(0, -1).split('\n');
  assert.ok(lines.length >= 150, `decode-cases.jsonl has ${lines.length} cases, want at least 150`);
  const entries = lines.map(line => JSON.parse(line));
  const names = new Set();
  let accepted = 0;
  for (const entry of entries) {
    assert.equal(typeof entry.name, 'string', 'name must be a string');
    assert.ok(entry.name && !names.has(entry.name), 'case names must be nonempty and unique');
    names.add(entry.name);
    assert.equal(typeof entry.valid, 'boolean', `${entry.name}: valid must be a boolean`);
    assert.equal(entry.canonical !== undefined, entry.valid, `${entry.name}: canonical presence must match valid`);
    assert.equal(entry.digest !== undefined, entry.valid, `${entry.name}: digest presence must match valid`);
    assert.notEqual(entry.input !== undefined, entry.inputHex !== undefined,
      `${entry.name}: exactly one of input and inputHex is required`);
    if (entry.valid) accepted++;
  }
  assert.ok(accepted > 0 && accepted < entries.length, 'corpus must contain both accepted and refused cases');
  return entries;
}

test('shared decode corpus rejects a malformed row', async () => {
  const corpus = await readFile(corpusURL, 'utf8');
  const entries = casesFromCorpus(corpus);
  delete entries[0].valid;
  const malformed = entries.map(entry => JSON.stringify(entry)).join('\n') + '\n';
  assert.throws(() => casesFromCorpus(malformed), /valid must be a boolean/);
});

test('shared decode corpus: acceptance, canonical bytes, digest and payload', async t => {
  const entries = casesFromCorpus(await readFile(corpusURL, 'utf8'));
  const encode = value => new TextEncoder().encode(value);
  for (const entry of entries) {
    await t.test(entry.name, async () => {
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
