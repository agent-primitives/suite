// Copyright (c) Microsoft Corporation. Licensed under the MIT License.
import { readdir, readFile } from 'node:fs/promises';

export async function fixtures() {
  const directory = new URL('../../testdata/', import.meta.url);
  const names = (await readdir(directory)).filter(name => name.endsWith('.json')).sort();
  if (names.length === 0) throw new Error('Missing shared policy fixtures');
  return Promise.all(names.map(async name => ({
    name,
    bytes: new Uint8Array(await readFile(new URL(name, directory))),
    digest: (await readFile(new URL(name.replace(/\.json$/, '.sha256'), directory), 'utf8')).trim(),
  })));
}
