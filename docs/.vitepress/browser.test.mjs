import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { createServer } from 'node:http'
import { mkdir, readFile, readdir } from 'node:fs/promises'
import path from 'node:path'
import { after, before, test } from 'node:test'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { latestRelease } from './release.mjs'

const root = fileURLToPath(new URL('dist/', import.meta.url))
// Every published schema must be linked from /schemas; derive the count so adding one can't silently skip the check.
const schemaCount = (await readdir(fileURLToPath(new URL('../../schema/', import.meta.url)))).filter(name => name.endsWith('.schema.json')).length
const catalog = JSON.parse(await readFile(new URL('../schema-catalog.json', import.meta.url), 'utf8'))
const publishedCount = catalog.bundles.reduce((count, bundle) => count + Object.keys(bundle.schemas).length, 0)
let browser, server, origin

before(async () => {
  server = createServer(async (req, res) => {
    try {
      const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname)
      let relative = pathname === '/' ? 'index.html' : pathname.slice(1)
      if (!path.extname(relative)) relative += '.html'
      const file = path.resolve(root, relative)
      if (!file.startsWith(root)) throw new Error('Outside site root')
      const types = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.woff2': 'font/woff2', '.svg': 'image/svg+xml', '.png': 'image/png' }
      res.setHeader('Content-Type', types[path.extname(file)] || 'application/octet-stream')
      res.end(await readFile(file))
    } catch {
      res.writeHead(404).end('Not found')
    }
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  origin = `http://127.0.0.1:${server.address().port}`
  browser = await chromium.launch()
})

after(async () => {
  try { await browser?.close() }
  finally { if (server) await new Promise(resolve => server.close(resolve)) }
})

async function ready(page, route = '/') {
  await page.goto(`${origin}${route}`, { waitUntil: 'networkidle' })
  await page.waitForFunction(() => document.querySelector('#app')?.__vue_app__)
}

async function assertClosedSidebarSkipped(page) {
  await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0) })
  for (let i = 0; i < 18; i++) {
    await page.keyboard.press('Tab')
    const focusedSidebar = await page.evaluate(() => !!document.activeElement?.closest('.VPSidebar'))
    assert.equal(focusedSidebar, false, `Tab ${i + 1} reached the closed sidebar`)
  }
}

test('landing content and release links remain available without JavaScript', async () => {
  const page = await browser.newPage({ javaScriptEnabled: false })
  try {
    await page.goto(origin)
    assert.equal(await page.getByRole('heading', { level: 1, name: 'AgentSuite' }).count(), 1)
    assert.equal(await page.getByRole('link', { name: latestRelease, exact: true }).getAttribute('href'), `https://github.com/agent-primitives/suite/tree/${latestRelease}`)
    assert.equal(await page.getByRole('link', { name: 'docs track main', exact: true }).getAttribute('href'), '/releases')
    assert.equal(await page.getByRole('link', { name: /Read the specification/ }).getAttribute('href'), '/spec')
  } finally { await page.close() }
})

test('landing and specification reflow at narrow, tablet and enlarged-text widths', async () => {
  const page = await browser.newPage({ reducedMotion: 'reduce' })
  try {
    for (const width of [320, 768, 960, 1440]) {
      await page.setViewportSize({ width, height: 1000 })
      for (const route of ['/', '/spec']) {
        await ready(page, route)
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${route} overflow at ${width}px`)
        await page.evaluate(() => { document.documentElement.style.fontSize = '200%' })
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${route} overflow at ${width}px with enlarged text`)
      }
    }
  } finally { await page.close() }
})

test('legacy specification fragments land beside their relocated sections', async () => {
  for (const [old, current] of [
    ['822-case-documents-and-assertions', '32-case-documents-and-assertions'],
    ['824-portable-evaluation-evidence', '42-portable-evaluation-evidence'],
    ['appendix-b-standalone-policy-contracts-normative', '52-standalone-policy-contracts-normative']
  ]) {
    // Each incoming URL starts fresh, without same-document history restoration.
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
    try {
      await ready(page, `/spec#${old}`)
      const alias = page.locator(`[id="${old}"]`)
      assert.equal(await alias.evaluate(el => el.parentElement.nextElementSibling?.id), current)
      await page.locator(`[id="${current}"]`).waitFor()
      await page.waitForFunction(id => {
        const bounds = document.getElementById(id)?.getBoundingClientRect()
        return bounds && bounds.top >= 0 && bounds.top < innerHeight
      }, current)
    } finally { await page.close() }
  }
})

for (const colorScheme of ['light', 'dark']) {
  for (const [device, viewport] of [['desktop', { width: 1440, height: 1000 }], ['mobile', { width: 390, height: 844 }]]) {
    test(`${device} reading paths, local search, raw downloads and theme (${colorScheme})`, async () => {
      const page = await browser.newPage({ viewport, colorScheme, reducedMotion: 'reduce' })
      const errors = [], external = []
      page.on('pageerror', error => errors.push(String(error)))
      page.on('request', request => { if (new URL(request.url()).origin !== origin) external.push(request.url()) })
      try {
        await ready(page)
        const fonts = await page.evaluate(async () => {
          await document.fonts.ready
          return [...document.fonts].filter(font => font.family === 'Public Sans' && font.status === 'loaded').map(font => font.weight)
        })
        assert.ok(fonts.includes('400') && fonts.includes('600 900'), 'Regular and semibold fonts must load, not silently fall back')
        const logo = page.locator('.VPNavBarTitle img.logo')
        assert.equal(await logo.evaluate(el => el.complete && el.naturalWidth > 0), true, 'Nav mark must decode')
        assert.equal((await logo.boundingBox()).height, 32)
        assert.equal(await page.locator('html').evaluate(el => el.classList.contains('dark')), colorScheme === 'dark')
        await page.keyboard.press('Tab')
        assert.equal(await page.evaluate(() => document.activeElement.getAttribute('href')), '#VPContent')
        const primary = page.getByRole('link', { name: /Read the specification/ })
        const bounds = await primary.boundingBox()
        assert.ok(bounds.y + bounds.height < viewport.height, 'Primary action must fit in the first viewport')
        for (const route of ['spec', 'schemas', 'go', 'conformance']) {
          assert.equal(await page.locator(`.suite-resources a[href="/${route}"]`).count(), 1)
        }
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
        await page.evaluate(() => document.activeElement?.blur())
        if (process.env.SCREENSHOT_DIR) {
          await mkdir(process.env.SCREENSHOT_DIR, { recursive: true })
          await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `after-${device}-${colorScheme}.png`), fullPage: true })
        }
        await primary.click()
        await page.waitForURL(`${origin}/spec`)
        await page.locator('[id="822-case-documents-and-assertions"]').waitFor({ state: 'attached' })
        await page.locator('[id="32-case-documents-and-assertions"]').waitFor()
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true)
        if (device === 'mobile') {
          const code = page.locator('.vp-doc pre').first()
          assert.equal(await code.evaluate(el => { el.scrollLeft = el.scrollWidth; return el.scrollLeft > 0 }), true, 'Long code scrolls locally')
        }
        if (process.env.SCREENSHOT_DIR) await page.screenshot({ path: path.join(process.env.SCREENSHOT_DIR, `after-spec-${device}-${colorScheme}.png`), fullPage: true })
        await ready(page, '/schemas')
        assert.equal(await page.locator('.vp-doc a[href^="/schema/"]').count(), schemaCount + publishedCount)
        for (const bundle of catalog.bundles) {
          for (const [name, expected] of Object.entries(bundle.schemas)) {
            const href = `/schema/${bundle.path}/${name}`
            assert.equal(await page.locator(`.vp-doc a[href="${href}"]`).count(), 1)
            const response = await page.request.get(`${origin}${href}`)
            assert.equal(response.status(), 200)
            const bytes = await response.body()
            assert.equal(createHash('sha256').update(bytes).digest('hex'), expected.sha256)
            assert.equal(JSON.parse(bytes).$id, expected.id)
          }
        }
        for (const [name, id] of [
          ['agent.schema.json', 'https://suite.agent-primitives.dev/schema/draft/agent.schema.json'],
          ['policy-v2.schema.json', 'https://suite.agent-primitives.dev/schema/draft/policy-v2.schema.json'],
          ['administrative-policy-v2.schema.json', 'https://suite.agent-primitives.dev/schema/draft/administrative-policy-v2.schema.json']
        ]) {
          const response = await page.request.get(`${origin}/schema/${name}`)
          assert.equal(response.status(), 200)
          assert.equal((await response.json()).$id, id)
        }
        await page.getByRole('button', { name: 'Search', exact: true }).click()
        await page.getByRole('searchbox').fill('canonical')
        await page.getByRole('link', { name: /canonical/i }).first().waitFor()
        await page.keyboard.press('Escape')
        await page.getByRole('searchbox').waitFor({ state: 'hidden' })
        if (device === 'mobile') await page.getByRole('button', { name: 'Site navigation', exact: true }).click()
        const appearance = page.getByRole('switch')
        await appearance.click()
        await page.waitForFunction(dark => document.documentElement.classList.contains('dark') === dark, colorScheme !== 'dark')
        assert.equal(await appearance.getAttribute('aria-checked'), String(colorScheme !== 'dark'))
        assert.deepEqual(errors, [])
        assert.deepEqual(external, [], 'No runtime third-party requests')
      } finally { await page.close() }
    })
  }
  test(`mobile navigation has distinct accessible names (${colorScheme})`, async () => {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, colorScheme, reducedMotion: 'reduce' })
    try {
      await ready(page, '/spec')
      assert.equal(await page.getByRole('button', { name: 'Site navigation', exact: true }).count(), 1)
      assert.equal(await page.getByRole('button', { name: 'Documentation', exact: true }).count(), 1)
      assert.equal(await page.getByRole('button', { name: 'Menu', exact: true }).count(), 0)
      const siteMenu = page.getByRole('button', { name: 'Site navigation', exact: true })
      await siteMenu.click()
      await page.locator('#VPNavScreen').waitFor({ state: 'visible' })
      await page.keyboard.press('Escape')
      await page.locator('#VPNavScreen').waitFor({ state: 'hidden' })
      assert.equal(await siteMenu.evaluate(el => el === document.activeElement), true)
    } finally { await page.close() }
  })

  test(`closed sidebar skips keyboard focus; open and desktop states remain reachable (${colorScheme})`, async () => {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, colorScheme, reducedMotion: 'reduce' })
    try {
      await ready(page, '/spec')
      await assertClosedSidebarSkipped(page)
      const trigger = page.locator('.VPLocalNav button[aria-controls="VPSidebarNav"]')
      const sidebar = page.locator('.VPSidebar')
      for (let cycle = 0; cycle < 2; cycle++) {
        await trigger.click()
        await sidebar.waitFor({ state: 'visible' })
        assert.equal(await trigger.getAttribute('aria-expanded'), 'true')
        let reachedSidebar = false
        for (let i = 0; i < 5; i++) {
          await page.keyboard.press('Tab')
          if (await sidebar.evaluate(el => el.contains(document.activeElement))) { reachedSidebar = true; break }
        }
        assert.equal(reachedSidebar, true, 'Open sidebar must remain keyboard-accessible')
        await page.keyboard.press('Escape')
        await sidebar.waitFor({ state: 'hidden' })
        assert.equal(await trigger.evaluate(el => el === document.activeElement), true, 'Escape returns focus to Documentation')
        await assertClosedSidebarSkipped(page)
      }
      await page.setViewportSize({ width: 1440, height: 1000 })
      await sidebar.waitFor({ state: 'visible' })
      await sidebar.getByRole('link', { name: 'Schemas', exact: true }).focus()
      assert.equal(await sidebar.evaluate(el => el.contains(document.activeElement)), true)
      await page.setViewportSize({ width: 390, height: 844 })
      await sidebar.waitFor({ state: 'hidden' })
      await assertClosedSidebarSkipped(page)
    } finally { await page.close() }
  })
}
