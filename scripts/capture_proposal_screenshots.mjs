import { createRequire } from 'module'

const require = createRequire(import.meta.url)
const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const projectRoot = path.resolve(process.cwd())
const outputDir = path.join(projectRoot, 'docs', 'assets', '方案文档')
fs.mkdirSync(outputDir, { recursive: true })

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({
  viewport: { width: 430, height: 900 },
  deviceScaleFactor: 2,
  colorScheme: 'light',
  locale: 'zh-CN',
})
const page = await context.newPage()
const consoleErrors = []
const failedResponses = []
page.on('console', (message) => {
  if (message.type() === 'error') consoleErrors.push(message.text())
})
page.on('pageerror', (error) => consoleErrors.push(error.message))
page.on('response', (response) => {
  if (response.status() >= 400) failedResponses.push({ status: response.status(), url: response.url() })
})

async function openRoute(route) {
  await page.goto(`http://localhost:5173${route}`, { waitUntil: 'networkidle' })
  await page.evaluate(async () => {
    if (document.fonts?.ready) await document.fonts.ready
    window.scrollTo(0, 0)
  })
  await page.waitForTimeout(250)
}

async function capture(name, route) {
  await openRoute(route)
  await page.screenshot({ path: path.join(outputDir, `${name}.png`) })
}

await capture('01-首页', '/')
const homeTextLength = (await page.locator('body').innerText()).trim().length
const hasErrorOverlay = await page.locator('.vite-error-overlay, #webpack-dev-server-client-overlay, [data-nextjs-dialog]').count()

await capture('02-录音', '/recording')
await capture('03-历史复盘', '/history')
await capture('04-复盘概览', '/review/demo-session')

await page.addStyleTag({ content: '.bottom-nav { display: none !important; }' })
await page.locator('.transcript-section').screenshot({ path: path.join(outputDir, '05-转写与洞察.png') })

await capture('06-重点时刻', '/moment/demo-session/topic-development-1')
await capture('07-定向练习', '/practice/topic-development-1')
await capture('08-个人目标', '/profile')
await capture('09-隐私与数据', '/data')

const result = {
  outputDir,
  screenshotCount: 9,
  homeTextLength,
  hasErrorOverlay: hasErrorOverlay > 0,
  consoleErrors,
  failedResponses,
}

console.log(JSON.stringify(result, null, 2))
await browser.close()
