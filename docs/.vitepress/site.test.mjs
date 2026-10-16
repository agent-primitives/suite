import assert from 'node:assert/strict'
import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../..', import.meta.url))
const dist = path.join(root, 'docs/.vitepress/dist')
const schemas = ['agent', 'build-profile', 'composition', 'eval-case', 'eval-evidence', 'eval-index', 'suite', 'tool-provider-composition', 'tool-provider'].map(name => `${name}.schema.json`).sort()
const html = name => readFile(path.join(dist, `${name}.html`), 'utf8')

test('all documentation pages render with root-based navigation and assets', async () => {
  const pages = ['404', 'index', 'spec', 'schemas', 'conformance', 'go', 'releases', 'hosting']
  assert.deepEqual((await readdir(dist)).filter(name => name.endsWith('.html')).sort(), pages.map(name => `${name}.html`).sort())
  for (const page of pages) {
    const content = await html(page)
    assert.doesNotMatch(content, /(?:href|src)="\/suite\//)
    assert.match(content, /(?:href|src)="\/assets\//)
  }
  const home = await html('index')
  for (const word of ['AgentSuite', 'kmx', 'agentsessions', 'Orka', 'planned']) assert.ok(home.includes(word))
  assert.match(home, /href="\/spec"/)
  assert.match(home, /https:\/\/github.com\/agent-primitives\/suite/)
})

test('the authoritative specification keeps every GitHub heading anchor', async () => {
  const { default: GithubSlugger } = await import('github-slugger')
  const slugger = new GithubSlugger()
  const source = await readFile(path.join(root, 'spec.md'), 'utf8')
  const content = await html('spec')
  let fenced = false
  let headings = 0
  for (const line of source.split('\n')) {
    if (/^```/.test(line)) fenced = !fenced
    if (fenced) continue
    const match = line.match(/^#{1,6}\s+(.+?)\s*#*$/)
    if (!match) continue
    const id = slugger.slug(match[1].replace(/[`*_]/g, ''))
    assert.ok(content.includes(`id="${id}"`), `missing heading ${id}`)
    headings++
  }
  assert.ok(headings > 50, 'must check the full spec, not an empty selection')
  assert.ok(content.includes('id="822-case-documents-and-assertions"'))
  assert.match(content, /href="\/schema\/eval-case.schema.json"/)
  const ref = process.env.GITHUB_SHA || 'main'
  assert.ok(content.includes(`https://github.com/agent-primitives/suite/tree/${ref}/testdata/coordinator-workers/`))
})

test('every downloadable schema is raw source JSON with its frozen ID', async () => {
  assert.deepEqual((await readdir(path.join(dist, 'schema'))).sort(), schemas)
  const downloads = await html('schemas')
  for (const name of schemas) {
    const source = await readFile(path.join(root, 'schema', name))
    assert.deepEqual(await readFile(path.join(dist, 'schema', name)), source, name)
    assert.equal(JSON.parse(source).$id, `https://kaimahi.dev/schemas/agentsuite/v1/${name}`)
    assert.ok(downloads.includes(`/schema/${name}`), `missing download ${name}`)
  }
  assert.equal(await readFile(path.join(dist, 'CNAME'), 'utf8'), 'suite.agent-primitives.dev\n')
})
