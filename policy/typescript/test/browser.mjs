// Copyright (c) Microsoft Corporation. Licensed under the MIT License.
// Serve real ESM on loopback; execute hashing/validation in Chromium, not Node.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { once } from 'node:events';
import { chromium } from 'playwright';
import { fixtures } from './fixtures.mjs';
import { cases } from './cases.mjs';

const files = new Map(await Promise.all(['index.js', 'json.js'].map(async name =>
  [`/dist/${name}`, await readFile(new URL(`../dist/${name}`, import.meta.url))])));
const server = createServer((request, response) => {
  const file = files.get(request.url);
  response.setHeader('Content-Type', file ? 'text/javascript' : 'text/html');
  response.end(file ?? '<!doctype html><title>Policy runtime test</title>');
});
let browser;
try {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  const vectors = (await fixtures()).map(vector => ({ ...vector, bytes: Buffer.from(vector.bytes).toString('base64') }));
  const explicit = cases().map(input => ({ ...input, data: Buffer.from(input.data).toString('base64') }));
  const result = await page.evaluate(async ({ vectors, explicit }) => {
    const api = await import('/dist/index.js');
    const fromBase64 = text => Uint8Array.from(atob(text), char => char.charCodeAt(0));
    const equal = (left, right) => left.length === right.length && left.every((value, i) => value === right[i]);
    for (const vector of vectors) {
      const bytes = fromBase64(vector.bytes);
      if (!equal(api.canonicalize(bytes), bytes)) throw new Error(`Browser bytes: ${vector.name}`);
      if (await api.digest(bytes) !== vector.digest) throw new Error(`Browser digest: ${vector.name}`);
      const payload = await api.payload(bytes);
      await api.verifyPayload(payload);
      payload.policyDigest = 'sha256:bad';
      let refused = false;
      try { await api.verifyPayload(payload); } catch { refused = true; }
      if (!refused) throw new Error('Browser accepted invalid payload');
    }
    for (const input of explicit) {
      let accepted = true;
      try { api.canonicalize(fromBase64(input.data)); } catch { accepted = false; }
      if (accepted !== input.accepted) throw new Error(`Browser acceptance: ${input.name}`);
    }
    return { vectors: vectors.length, cases: explicit.length, secureContext: isSecureContext };
  }, { vectors, explicit });
  assert.equal(result.secureContext, true, 'Web Crypto requires a secure context');
  console.log(`Chromium ${browser.version()}: ${result.vectors} shared vectors (bytes/digest/payload), ${result.cases} explicit cases passed`);
} finally {
  if (browser) await browser.close();
  server.close();
  server.closeAllConnections();
}
