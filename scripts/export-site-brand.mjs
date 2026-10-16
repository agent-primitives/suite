import { readFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

// Documentation dependencies live under docs/, not the repository root.
const require = createRequire(new URL('../docs/package.json', import.meta.url))
const { chromium } = require('playwright')
const brand = new URL('../docs/public/brand/', import.meta.url)
const mark = await readFile(new URL('agentsuite.svg', brand), 'utf8')
const regular = await readFile(new URL('../docs/public/fonts/PublicSans-Regular.woff2', import.meta.url))
const semibold = await readFile(new URL('../docs/public/fonts/PublicSans-SemiBold.woff2', import.meta.url))
const browser = await chromium.launch()

try {
  const page = await browser.newPage({ viewport: { width: 512, height: 512 }, deviceScaleFactor: 1 })
  await page.setContent(`<style>body{margin:0}svg{display:block;width:512px;height:512px}</style>${mark}`)
  await page.screenshot({ path: fileURLToPath(new URL('agentsuite.png', brand)), omitBackground: true })

  await page.setViewportSize({ width: 1280, height: 640 })
  await page.setContent(`<!doctype html><html lang="en"><meta charset="utf-8"><title>AgentSuite social preview</title>
    <style>
      @font-face{font-family:Public;src:url(data:font/woff2;base64,${regular.toString('base64')}) format('woff2');font-weight:400}
      @font-face{font-family:Public;src:url(data:font/woff2;base64,${semibold.toString('base64')}) format('woff2');font-weight:600}
      *{box-sizing:border-box}body{margin:0;width:1280px;height:640px;padding:64px 80px;background:oklch(98.5% 0.005 155);color:oklch(25% 0.022 155);font-family:Public,sans-serif}
      .family{font-size:22px;color:oklch(43% 0.02 155)}.identity{display:flex;align-items:center;gap:40px;margin-top:64px}
      svg{width:152px;height:152px;flex-shrink:0}h1{font-size:88px;letter-spacing:-5px;font-weight:600;margin:0;line-height:1.1}
      .description{font-size:30px;line-height:1.5;margin:40px 0 0;white-space:nowrap;letter-spacing:-0.6px}
      .url{margin-top:72px;padding-top:24px;border-top:1px solid oklch(86% 0.012 155);font-size:22px;color:oklch(43% 0.02 155)}
    </style>
    <body><div class="family">agent-primitives / suite</div>
    <div class="identity">${mark}<h1>AgentSuite</h1></div>
    <p class="description">Content-addressed agent definitions, packaged as OCI artifacts.</p>
    <div class="url">suite.agent-primitives.dev</div></body></html>`)
  await page.evaluate(() => document.fonts.ready)
  const fits = await page.locator('.description').evaluate(el => el.scrollWidth <= el.clientWidth)
  if (!fits) throw new Error('Social preview description does not fit on one line')
  await page.screenshot({ path: fileURLToPath(new URL('social-preview.png', brand)) })
  await page.close()
  console.log('Exported brand/agentsuite.png (512×512) and brand/social-preview.png (1280×640)')
} finally {
  await browser.close()
}
