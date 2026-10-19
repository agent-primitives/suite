import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { latestRelease } from './release.mjs'

const root = fileURLToPath(new URL('../..', import.meta.url))
const dist = path.join(root, 'docs/.vitepress/dist')
const schemas = ['administrative-policy-v2', 'agent', 'build-profile', 'composition', 'eval-case', 'eval-evidence', 'eval-index', 'execution', 'inference', 'policy-v2', 'runtime-profile', 'suite', 'tool-provider-composition', 'tool-provider'].map(name => `${name}.schema.json`).sort()
const html = name => readFile(path.join(dist, `${name}.html`), 'utf8')
const catalog = JSON.parse(await readFile(path.join(root, 'docs/schema-catalog.json'), 'utf8'))

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

test('the landing page exposes the format and release-first reading paths without JavaScript', async () => {
  const home = await html('index')
  const article = home.match(/<main class="suite-home"[\s\S]*?<\/main>/)?.[0]
  assert.ok(article, 'the format overview must be server-rendered')
  assert.match(article, /docs track main/)
  for (const route of ['spec', 'schemas', 'go', 'conformance']) {
    assert.ok(article.includes(`href="/${route}"`), `missing ${route} entry point`)
  }
  for (const term of ['agentsuite.json', 'ToolProviders', 'canonical', 'exact bytes', 'does not execute']) {
    assert.ok(article.includes(term), `missing format boundary: ${term}`)
  }
})

test('status and footer labels and links agree with the latest release constant', async () => {
  const home = await html('index')
  const links = [...home.matchAll(/<a href="([^"]+)"[^>]*>(v\d+\.\d+\.\d+(?: tag)?)<\/a>/g)]
    .map(([, href, text]) => ({ href, text }))
  const href = `https://github.com/agent-primitives/suite/tree/${latestRelease}`
  assert.deepEqual(links, [{ href, text: latestRelease }, { href, text: `${latestRelease} tag` }])
})

test('the validation section links the portable evidence verifier to its spec section', async () => {
  const home = await html('index')
  const section = home.match(/<section class="suite-validation"[\s\S]*?<\/section>/)?.[0] || ''
  assert.ok(section.includes('v0.2.0 adds portable evaluation evidence with an offline verifier'))
  assert.ok(section.includes('href="/spec#824-portable-evaluation-evidence"'))
  assert.ok(section.includes('VerifyEvaluation'))
  assert.ok((await html('spec')).includes('id="824-portable-evaluation-evidence"'))
})

test('the geometric mark ships as nav logo, favicon and correctly sized PNG exports', async () => {
  const home = await html('index')
  assert.match(home, /rel="icon"[^>]*href="\/brand\/agentsuite.svg"/)
  assert.match(home, /class="[^\"]*logo[^\"]*"[^>]*src="\/brand\/agentsuite.svg"/)
  const mark = await readFile(path.join(dist, 'brand/agentsuite.svg'), 'utf8')
  assert.match(mark, /viewBox="0 0 64 64"/)
  assert.doesNotMatch(mark, /<script|https?:\/\/(?!www\.w3\.org)/)
  for (const [file, width, height] of [['agentsuite.png', 512, 512], ['social-preview.png', 1280, 640]]) {
    const png = await readFile(path.join(dist, 'brand', file))
    assert.deepEqual([...png.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10])
    assert.equal(png.readUInt32BE(16), width, file)
    assert.equal(png.readUInt32BE(20), height, file)
  }
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
  const historyRoots = [...new Set(catalog.bundles.map(bundle => bundle.path.split('/')[0]))]
  assert.deepEqual((await readdir(path.join(dist, 'schema'))).sort(), [...schemas, 'catalog.json', ...historyRoots].sort())
  assert.deepEqual(JSON.parse(await readFile(path.join(dist, 'schema/catalog.json'), 'utf8')), catalog)
  for (const bundle of catalog.bundles) {
    assert.deepEqual((await readdir(path.join(dist, 'schema', bundle.path))).sort(), Object.keys(bundle.schemas).sort())
    for (const [name, expected] of Object.entries(bundle.schemas)) {
      const bytes = await readFile(path.join(dist, 'schema', bundle.path, name))
      assert.equal(createHash('sha256').update(bytes).digest('hex'), expected.sha256)
      assert.equal(JSON.parse(bytes).$id, expected.id)
    }
  }
  const downloads = await html('schemas')
  for (const name of schemas) {
    const source = await readFile(path.join(root, 'schema', name))
    assert.deepEqual(await readFile(path.join(dist, 'schema', name)), source, name)
    assert.equal(JSON.parse(source).$id, `https://suite.agent-primitives.dev/schema/v0.5/${name}`)
    assert.ok(downloads.includes(`/schema/${name}`), `missing download ${name}`)
  }
  assert.equal(await readFile(path.join(dist, 'CNAME'), 'utf8'), 'suite.agent-primitives.dev\n')
})
