// Real Chromium + real service worker + real IndexedDB, with a deterministic API fixture.
import {chromium} from 'playwright';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve, extname} from 'node:path';
import assert from 'node:assert/strict';
const root = resolve('av_field/public/pwa');
let user = 'agent@example.com', expired = false;
const acknowledgements = new Map();
const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname.startsWith('/api/method/av_field.api.')) {
      res.setHeader('Content-Type', 'application/json'); res.setHeader('Cache-Control', 'no-store');
      if (expired) { res.writeHead(403); res.end(JSON.stringify({exc_type:'PermissionError'})); return; }
      const method = url.pathname.split('.').at(-1);
      let message;
      if (method === 'context') message = {user, csrf_token:'fixture-token', version:1};
      else if (method === 'references') {
        assert.equal(url.searchParams.get('expected_user'), user);
        message = {rows:url.searchParams.get('kind') === 'customers' ? [{name:'CUST-1',customer_name:'Test Shop'}] : [{name:'ITEM-1',item_name:'Test Item',stock_uom:'Nos'}],after:null};
      }
      else if (method === 'push') {
        assert.equal(req.headers['x-frappe-csrf-token'], 'fixture-token');
        let body = ''; for await (const chunk of req) body += chunk;
        const parsed = JSON.parse(body); assert.equal(parsed.expected_user, user);
        const op = parsed.operation;
        message = {id:op.id,name:`FIELD-${op.id}`,doctype:op.kind === 'visit' ? 'Field Visit' : 'Field Order Request',duplicate:acknowledgements.has(`${user}:${op.id}`)};
        acknowledgements.set(`${user}:${op.id}`, op);
      } else { res.writeHead(404); res.end('{}'); return; }
      res.end(JSON.stringify({message})); return;
    }
    const path = url.pathname.replace('/assets/av_field/pwa/', '');
    if (path.includes('..') || !url.pathname.startsWith('/assets/av_field/pwa/')) { res.writeHead(404); res.end(); return; }
    const data = await readFile(resolve(root, path));
    const type = {'.html':'text/html','.js':'application/javascript','.css':'text/css','.png':'image/png','.webmanifest':'application/manifest+json'}[extname(path)];
    res.setHeader('Content-Type',type || 'text/plain'); res.end(data);
  } catch { res.writeHead(500); res.end('{}'); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
try {
  browser = await chromium.launch({headless:true, executablePath:process.env.CHROMIUM_EXECUTABLE || undefined, args:process.env.CHROMIUM_EXECUTABLE ? ["--no-sandbox", "--disable-dev-shm-usage"] : []});
  const context = await browser.newContext({viewport:{width:390,height:844}});
  const page = await context.newPage(); const errors=[]; page.on('pageerror',error=>errors.push(error.message));
  const url = `http://127.0.0.1:${server.address().port}/assets/av_field/pwa/index.html`;
  await page.goto(url);
  await page.waitForFunction(() => document.querySelector('#message').textContent.includes('up to date'));
  await page.evaluate(async () => {await navigator.serviceWorker.ready});
  await page.reload(); await page.waitForFunction(() => document.querySelector('#workspace').hidden === false);
  await page.waitForFunction(() => !document.querySelector('#sync-now').disabled);
  assert.ok(await page.evaluate(() => !!navigator.serviceWorker.controller));
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile UI must not overflow horizontally');
  if (process.env.SCREENSHOT_DIR) await page.screenshot({path: `${process.env.SCREENSHOT_DIR}/av-field-mobile.png`, fullPage: true});
  await context.setOffline(true);
  await page.locator('#visit-form select').selectOption('CUST-1');
  await page.locator('#visit-form textarea').fill('Offline visit');
  await page.locator('#visit-form button[type=submit]').click();
  await page.waitForFunction(() => document.querySelector('#pending-count').textContent === '1');
  await page.locator('nav button[data-view=order]').click();
  await page.locator('#order-form select.customers').selectOption('CUST-1');
  await page.locator('.item-select').selectOption('ITEM-1'); await page.locator('.qty').fill('3');
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Order grid must fit mobile viewport');
  await page.locator('#order-form button[type=submit]').click();
  await page.waitForFunction(() => document.querySelector('#pending-count').textContent === '2');
  await page.reload();
  await page.waitForFunction(() => document.querySelector('#workspace').hidden === false);
  assert.equal(await page.locator('#pending-count').textContent(), '2');
  // Shell cache must contain no private/API responses.
  const cached = await page.evaluate(async () => {const cache=await caches.open('av-field-shell-16.0.1');return (await cache.keys()).map(req=>req.url)});
  assert.ok(cached.every(url => url.includes('/assets/av_field/pwa/')));
  await context.setOffline(false);
  // CDP offline emulation does not emit connectivity events in every Chromium version.
  // Exercise the actual reconnection handler explicitly, independently of transport emulation.
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await page.waitForFunction(() => document.querySelector('#pending-count').textContent === '0');
  assert.equal(acknowledgements.size,2);
  // Opening a different signed-in account cannot upload or show the previous account's data.
  user = 'other@example.com'; await page.reload();
  await page.waitForFunction(() => document.querySelector('#identity').textContent === 'other@example.com');
  assert.equal(await page.locator('#visits-count').textContent(), '0');
  user = 'agent@example.com'; await page.reload();
  await page.waitForFunction(() => document.querySelector('#identity').textContent === 'agent@example.com');
  assert.equal(await page.locator('#visits-count').textContent(), '1');
  expired = true; await page.locator('nav button[data-view=sync]').click(); await page.locator('#sync-now').click();
  await page.waitForFunction(() => !document.querySelector('#locked').hidden);
  assert.equal(acknowledgements.size,2); assert.deepEqual(errors,[]);
  if (process.env.SCREENSHOT_DIR) {
    expired = false; await page.setViewportSize({width:1440,height:1000}); await page.reload();
    await page.waitForFunction(() => document.querySelector('#workspace').hidden === false && !document.querySelector('#sync-now').disabled);
    await page.screenshot({path: `${process.env.SCREENSHOT_DIR}/av-field-desktop.png`, fullPage: true});
  }
  console.log('PASS: offline reload, visit/order capture, IndexedDB persistence, reconnection sync, account isolation, session expiry, public-only cache, mobile layout');
} finally {if(browser) await browser.close(); await new Promise(resolve=>server.close(resolve));}
