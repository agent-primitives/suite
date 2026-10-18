// Copyright (c) Microsoft Corporation. Licensed under the MIT License.
import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createInterface } from 'node:readline';
import { once } from 'node:events';
import test, { after } from 'node:test';
import { canonicalize, decodePolicy, digest, payload, verifyPayload } from '../dist/index.js';
import { cases, generatedCases, encode, v1, v2 } from './cases.mjs';
import { fixtures } from './fixtures.mjs';

async function accepts(action) {
  try { await action(); return true; }
  catch { return false; } // Deliberate: the test compares refusal, not error wording.
}

let oracleBuild;
let oracleDirectory;
after(async () => {
  if (oracleDirectory) await rm(oracleDirectory, { recursive: true, force: true });
});

async function oracle(t) {
  oracleBuild ??= (async () => {
    oracleDirectory = await mkdtemp(join(tmpdir(), 'suite-policy-'));
    const binary = join(oracleDirectory, 'oracle');
    execFileSync('go', ['build', '-o', binary, 'test/oracle/main.go'], {
      cwd: new URL('../', import.meta.url), stdio: 'pipe', timeout: 120_000,
      env: { ...process.env, GOWORK: 'off' },
    });
    return binary;
  })();
  const binary = await oracleBuild;
  const child = spawn(binary, [], { stdio: ['pipe', 'pipe', 'inherit'] });
  const lines = createInterface({ input: child.stdout })[Symbol.asyncIterator]();
  t.after(async () => {
    const exit = once(child, 'exit');
    child.stdin.end();
    const [code] = await exit;
    assert.equal(code, 0, 'Go oracle exit');
  });
  return async (data, envelope) => {
    const request = { data: Buffer.from(data).toString('base64') };
    if (envelope) request.payload = { ...envelope, policyBytes: Buffer.from(envelope.policyBytes).toString('base64') };
    child.stdin.write(JSON.stringify(request) + '\n');
    const { value, done } = await lines.next();
    assert.equal(done, false, 'Go oracle must respond');
    return JSON.parse(value);
  };
}

test('every shared vector: exact bytes, digest, payload and no aliasing', async () => {
  const vectors = await fixtures();
  for (const vector of vectors) {
    assert.deepEqual(canonicalize(vector.bytes), vector.bytes, vector.name);
    assert.equal(await digest(vector.bytes), vector.digest, vector.name);
    const result = await payload(vector.bytes);
    assert.deepEqual(result.policyBytes, vector.bytes);
    assert.equal(result.policyDigest, vector.digest);
    await verifyPayload(result);
    const original = vector.bytes.slice();
    const decoded = decodePolicy(vector.bytes);
    if ('denyWritePaths' in decoded) decoded.denyWritePaths.push('/new');
    else decoded.network.egressAllow.push({ address: '1.2.3.4', protocol: 'TCP', port: 1 });
    result.policyBytes[0] = 0;
    assert.deepEqual(vector.bytes, original, 'outputs never alias input bytes');
  }
});

test('raw decoding/canonicalization and payload verification agree with actual Go', { timeout: 120_000 }, async t => {
  const ask = await oracle(t);
  const inputs = [
    ...(await fixtures()).map(vector => ({ name: vector.name, data: vector.bytes, accepted: true })),
    ...cases(), ...generatedCases(),
  ];
  let accepted = 0;
  for (const input of inputs) {
    const go = await ask(input.data);
    let tsBytes;
    const tsAccepted = await accepts(() => { tsBytes = canonicalize(input.data); });
    assert.equal(tsAccepted, go.accepted, `${input.name}: acceptance parity`);
    if (input.accepted !== undefined) {
      assert.equal(go.accepted, input.accepted, `${input.name}: independently expected Go result`);
    }
    if (tsAccepted) {
      accepted++;
      assert.deepEqual(tsBytes, new Uint8Array(Buffer.from(go.canonical, 'base64')), `${input.name}: bytes`);
      assert.equal(await digest(tsBytes), go.digest, `${input.name}: digest`);
      // Also compare verification of raw bytes, not just the normalized result.
      const policy = decodePolicy(input.data);
      const envelope = { version: policy.version, requiredCapabilities: policy.requiredCapabilities,
        policyBytes: input.data, policyDigest: await digest(input.data) };
      const verified = await ask(input.data, envelope);
      assert.equal(await accepts(() => verifyPayload(envelope)), verified.verified, `${input.name}: raw verify`);
    }
  }
  assert.ok(accepted > 200, 'generated accepted cases must actually run');
  t.diagnostic(`${inputs.length} deterministic raw cases, ${accepted} accepted with exact bytes/digests`);

  let envelopes = 0;
  for (const vector of await fixtures()) {
    const valid = await payload(vector.bytes);
    const candidates = [valid];
    for (const version of ['', 'agentsuite.policy/v3', valid.version.endsWith('v1') ? 'agentsuite.policy/v2' : 'agentsuite.policy/v1']) {
      candidates.push({ ...valid, version });
    }
    for (const requiredCapabilities of [[], null, ['unknown'], [...valid.requiredCapabilities, ...valid.requiredCapabilities],
      [valid.version.endsWith('v1') ? 'network/egress-allow/v1' : 'filesystem/deny-write/v1']]) {
      candidates.push({ ...valid, requiredCapabilities });
    }
    for (const policyDigest of ['', valid.policyDigest.toUpperCase(), valid.policyDigest.slice(7), valid.policyDigest + '\n',
      valid.policyDigest.replace(/.$/, valid.policyDigest.endsWith('0') ? '1' : '0')]) {
      candidates.push({ ...valid, policyDigest });
    }
    for (const policyBytes of [encode(' ' + new TextDecoder().decode(vector.bytes)),
      encode(new TextDecoder().decode(vector.bytes) + '\n'), encode('{}'), encode('null'),
      encode(JSON.stringify(v1(['/different']))), encode(JSON.stringify(v2([]))),
      encode(new TextDecoder().decode(vector.bytes).replace('"version":', '"Version":'))]) {
      candidates.push({ ...valid, policyBytes, policyDigest: await digest(policyBytes) });
      candidates.push({ ...valid, policyBytes });
    }
    for (const envelope of candidates) {
      const go = await ask(vector.bytes, envelope);
      assert.equal(await accepts(() => verifyPayload(envelope)), go.verified, `envelope ${vector.name} #${envelopes}`);
      envelopes++;
    }
  }
  t.diagnostic(`${envelopes} payload verification differential cases`);
});

test('strict parser and all explicit refusal/acceptance expectations', () => {
  for (const input of cases()) {
    if (input.accepted) assert.doesNotThrow(() => decodePolicy(input.data), input.name);
    else assert.throws(() => decodePolicy(input.data), undefined, input.name);
  }
});

test('long compensated port spelling preserves canonical Go identity', async t => {
  const ask = await oracle(t);
  const ordinary = encode(v2([{ address: '192.0.2.1', protocol: 'TCP', port: 1 }]));
  const text = new TextDecoder().decode(ordinary);
  const exact = '1' + '0'.repeat(800) + 'e-800';
  const raw = encode(text.replace('"port":1', '"port":' + exact));
  assert.equal(decodePolicy(raw).network.egressAllow[0].port, 1);
  const normalized = canonicalize(raw);
  const result = await payload(raw);
  assert.deepEqual(result.policyBytes, normalized);
  await verifyPayload(result);

  const go = await ask(ordinary, result);
  assert.equal(go.accepted, true, 'Go accepts the ordinary integer spelling');
  assert.equal(go.verified, true, 'Go verifies the TS canonical payload');
  assert.deepEqual(normalized, new Uint8Array(Buffer.from(go.canonical, 'base64')));
  assert.equal(result.policyDigest, go.digest);
  assert.equal(await digest(normalized), go.digest);

  const fractional = '1' + '0'.repeat(799) + '1e-800';
  const rounded = encode(text.replace('"port":1', '"port":' + fractional));
  assert.throws(() => decodePolicy(rounded), 'A fraction rounding to 1 must refuse');
  assert.throws(() => canonicalize(rounded));
  await assert.rejects(payload(rounded));

  // Go 1.26.0's float precheck misreads this exact integer (golang/go#42436).
  // Do not require that bug to persist when the Go toolchain is upgraded.
  const rawGo = await ask(raw);
  if (rawGo.accepted) {
    assert.deepEqual(normalized, new Uint8Array(Buffer.from(rawGo.canonical, 'base64')));
    assert.equal(result.policyDigest, rawGo.digest);
    t.diagnostic('Go accepts the compensated spelling with matching canonical identity');
  } else {
    t.diagnostic('Known Go raw-number refusal; canonical payload interoperability passed');
  }
});

test('payload verification snapshots mutable bytes before awaiting SHA-256', async () => {
  const result = await payload(encode(v1(['/x'])));
  const promise = verifyPayload(result);
  result.policyBytes.fill(0);
  result.version = 'changed';
  result.requiredCapabilities.length = 0;
  result.policyDigest = 'changed';
  await promise;
});
