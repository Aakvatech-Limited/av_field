import {openStore} from './db.js';
import {ApiError, drain, downloadReferences} from './sync.js';
const $ = selector => document.querySelector(selector);
const ownerKey = 'av-field:last-user';
let store, user, csrf, busy = false, locationData = null, snapshot = {customers: [], items: []};
let booting = false, locked = true;
function tell(text, error = false) { $('#message').textContent = text; $('#message').classList.toggle('error', error); $('#message').hidden = false; }
function lock(reason) { locked = true; csrf = null; $('#workspace').hidden = true; $('#locked').hidden = false; $('#lock-reason').textContent = reason; }
function unlock() { locked = false; $('#workspace').hidden = false; $('#locked').hidden = true; }
function connection() { const el = $('#connection'); el.textContent = busy ? 'Syncing…' : navigator.onLine ? 'Online' : 'Offline'; el.className = `pill ${navigator.onLine ? 'online' : 'offline'}`; }
async function api(method, args = {}, post = false) {
  const url = new URL(`/api/method/av_field.api.${method}`, window.location.origin);
  if (!post) Object.entries(args).forEach(([key, value]) => url.searchParams.set(key, value));
  const response = await fetch(url, {method: post ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store',
    signal: AbortSignal.timeout(30000), headers: post ? {'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': csrf} : {},
    body: post ? JSON.stringify(args) : undefined});
  let data;
  try { data = await response.json(); } catch { throw new ApiError('Unexpected server response. Check your ERPNext connection.', response.status >= 400 ? response.status : 503); }
  if (!response.ok || data.exc || data.exc_type) {
    let message = `Server rejected the request (${response.status}).`;
    try { const messages = JSON.parse(data._server_messages || '[]'); if (messages.length) message = JSON.parse(messages[0]).message; } catch { /* use safe fallback */ }
    // Server messages may contain HTML. They are rendered with textContent only.
    throw new ApiError(message, response.status || 500);
  }
  return data.message;
}
async function verifySession() {
  const context = await api('context');
  if (context.version !== 1 || !context.user || !context.csrf_token) throw new ApiError('Unsupported server sync contract', 409);
  if (user && context.user !== user) {
    lock('The signed-in account changed. Reload to open its separate storage. Return to the original account to sync its pending records.');
    throw new ApiError('Account changed. Reload the app.', 403);
  }
  csrf = context.csrf_token;
  return context.user;
}
function option(value, label) { const el = document.createElement('option'); el.value = value; el.textContent = label; return el; }
function fillSelect(select, rows, label, placeholder) {
  const current = select.value;
  select.replaceChildren(option('', placeholder), ...rows.map(row => option(row.name, label(row))));
  select.value = current;
}
function renderMasters() {
  document.querySelectorAll('.customers').forEach(select => fillSelect(select, snapshot.customers, row => `${row.customer_name} · ${row.name}`, 'Select a customer'));
  document.querySelectorAll('.item-select').forEach(select => fillSelect(select, snapshot.items, row => `${row.item_name} · ${row.stock_uom}`, 'Select an item'));
  $('#master-summary').textContent = snapshot.downloadedAt ? `${snapshot.customers.length} customers · ${snapshot.items.length} items. Last downloaded ${new Date(snapshot.downloadedAt).toLocaleString()}.` : 'No offline master data downloaded yet. Sync while online to get started.';
}
async function render() {
  if (!store) return;
  const operations = await store.list();
  $('#visits-count').textContent = operations.filter(op => op.kind === 'visit').length;
  $('#orders-count').textContent = operations.filter(op => op.kind === 'order').length;
  $('#pending-count').textContent = operations.filter(op => op.status !== 'synced').length;
  const list = $('#activity-list'); list.replaceChildren();
  if (!operations.length) { const p = document.createElement('p'); p.className = 'hint'; p.textContent = 'Your visits and order requests will appear here.'; list.append(p); }
  operations.sort((a,b) => b.recorded_at.localeCompare(a.recorded_at)).slice(0,100).forEach(op => {
    const entry = document.createElement('article'); entry.className = 'activity';
    const title = document.createElement('strong'); title.textContent = `${op.kind === 'visit' ? 'Visit' : 'Order request'} · ${op.payload.customer}`;
    const status = document.createElement('span'); status.className = `status ${op.status}`; status.textContent = op.status;
    const detail = document.createElement('p'); detail.textContent = `${new Date(op.recorded_at).toLocaleString()}${op.kind === 'order' ? ` · ${op.payload.items.length} item(s)` : ''} · ${op.payload.notes || 'No notes'}`;
    entry.append(title, status, detail);
    if (op.error) { const error = document.createElement('p'); error.textContent = op.error; entry.append(error); }
    if (op.ack) {
      const link = document.createElement('a'); link.className = 'text-button'; link.textContent = 'Open in ERPNext';
      link.href = `/app/${op.ack.doctype === 'Field Visit' ? 'field-visit' : 'field-order-request'}/${encodeURIComponent(op.ack.name)}`; link.target = '_blank'; link.rel = 'noopener'; entry.append(link);
    } else {
      const retry = document.createElement('button'); retry.className = 'text-button'; retry.textContent = 'Retry sync'; retry.disabled = busy;
      retry.onclick = () => action(async () => { await store.save({...op, status: 'pending', nextAttemptAt: null}); await sync(); });
      entry.append(retry);
    }
    list.append(entry);
  });
}
async function sync() {
  if (busy || !store || locked) return;
  busy = true; connection(); $('#sync-now').disabled = true;
  try {
    const work = async () => {
      await verifySession();
      await drain(store, operation => api('push', {operation, expected_user: user}, true));
      const fresh = await downloadReferences((kind, after) => api('references', {kind, after, expected_user: user}));
      await store.replaceReferences(fresh); snapshot = fresh; renderMasters();
      const records = await store.list();
      const rejected = records.filter(op => op.status === 'rejected').length;
      const pending = records.filter(op => op.status === 'pending').length;
      tell(rejected ? `${rejected} record(s) need attention in Activity. Offline masters refreshed.` : pending ? `${pending} record(s) still awaiting sync. Offline masters refreshed.` : 'Records synced. Your offline customers and items are up to date.', !!rejected);
    };
    if (navigator.locks) await navigator.locks.request(`av-field-sync:${user}`, work); else await work();
  } catch (error) {
    if ([401,403].includes(error.status)) lock('Sign in with the same account to continue. Your device records are preserved.');
    tell(error.status ? error.message : 'Connection unavailable. Saved records stay on this device; sync will retry while the app is open.', true);
  } finally { busy = false; $('#sync-now').disabled = false; connection(); await render(); }
}
async function action(fn) { try { await fn(); } catch(error) { tell(error.message || 'The action failed. Please try again.', true); } }
async function save(kind, payload) {
  if (locked || !store) throw new Error('Sign in and initialise this device before capturing records.');
  const operation = {version: 1, id: crypto.randomUUID(), kind, recorded_at: new Date().toISOString(), payload, status: 'pending'};
  await store.save(operation); // UI confirms only after the IndexedDB transaction commits.
  tell(`${kind === 'visit' ? 'Visit' : 'Order request'} saved on this device. ${navigator.onLine ? 'Ready to sync.' : 'It will sync when you reconnect.'}`);
  await render();
  return operation;
}
function addLine() {
  if ($('#order-lines').children.length >= 100) { tell('An order supports at most 100 lines.', true); return; }
  const row = document.createElement('div'); row.className = 'line';
  row.innerHTML = '<label>Item<select class="item-select" required></select></label><label>Quantity<input class="qty" type="number" min="0.000001" max="1000000" step="0.000001" value="1" required></label><button type="button" aria-label="Remove item">×</button>';
  row.querySelector('button').onclick = () => row.remove(); $('#order-lines').append(row); renderMasters();
}
$('#visit-form').onsubmit = event => { event.preventDefault(); action(async () => {
  const button = event.target.querySelector('[type="submit"]'); button.disabled = true;
  try { const data = new FormData(event.target); await save('visit', {customer: data.get('customer'), notes: data.get('notes'), ...(locationData || {})}); event.target.reset(); clearLocation(); if (navigator.onLine) void sync(); } finally { button.disabled = false; }
}); };
$('#order-form').onsubmit = event => { event.preventDefault(); action(async () => {
  const button = event.target.querySelector('[type="submit"]'); button.disabled = true;
  try {
    const data = new FormData(event.target); const rows = [...document.querySelectorAll('.line')];
    const items = rows.map(row => ({item_code: row.querySelector('select').value, qty: Number(row.querySelector('input').value)}));
    if (!items.length || items.some(item => !item.item_code || !Number.isFinite(item.qty) || item.qty <= 0 || item.qty > 1000000)) throw new Error('Choose at least one item and enter positive quantities.');
    if (new Set(items.map(item => item.item_code)).size !== items.length) throw new Error('Combine duplicate items into a single row.');
    await save('order', {customer: data.get('customer'), notes: data.get('notes'), items});
    event.target.reset(); $('#order-lines').replaceChildren(); addLine(); if (navigator.onLine) void sync();
  } finally { button.disabled = false; }
}); };
function clearLocation() { locationData = null; $('#clear-location').hidden = true; $('#location-label').textContent = 'Optional · capture only when you choose'; }
$('#clear-location').onclick = clearLocation;
$('#capture-location').onclick = () => {
  if (!navigator.geolocation) { tell('Location capture is not available in this browser.', true); return; }
  $('#capture-location').disabled = true; $('#visit-form button[type="submit"]').disabled = true;
  navigator.geolocation.getCurrentPosition(position => {
    locationData = {latitude: position.coords.latitude, longitude: position.coords.longitude, accuracy: position.coords.accuracy};
    $('#location-label').textContent = `Captured ${locationData.latitude.toFixed(5)}, ${locationData.longitude.toFixed(5)} · accuracy ±${Math.round(locationData.accuracy)} m`;
    $('#clear-location').hidden = false; $('#capture-location').disabled = false; $('#visit-form button[type="submit"]').disabled = false;
  }, error => { $('#capture-location').disabled = false; $('#visit-form button[type="submit"]').disabled = false; tell(`Location unavailable: ${error.message}. You can save the visit without it.`, true); }, {enableHighAccuracy: true, timeout: 15000, maximumAge: 0});
};
$('#add-line').onclick = addLine;
document.querySelectorAll('nav button').forEach(button => button.onclick = () => {
  document.querySelectorAll('nav button').forEach(el => el.classList.toggle('active', el === button));
  document.querySelectorAll('.view').forEach(el => el.hidden = el.id !== `view-${button.dataset.view}`);
});
$('#sync-now').onclick = () => sync();
$('#unlock').onclick = () => boot();
$('#export').onclick = () => action(async () => {
  const blob = new Blob([JSON.stringify({user, exported_at: new Date().toISOString(), operations: await store.list()}, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `av-field-${new Date().toISOString().slice(0,10)}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$('#erase').onclick = () => action(async () => {
  if (busy) throw new Error('Wait for sync to finish before clearing device data.');
  if ((await store.list()).some(op => op.status !== 'synced')) throw new Error('Sync all pending and rejected records before clearing this account’s device data.');
  if (!confirm('Clear this account’s local records and offline customers/items? Server records remain available in ERPNext.')) return;
  await store.clear(); localStorage.removeItem(ownerKey); store.close(); store = null; user = null; csrf = null; snapshot = {customers: [], items: []};
  $('#identity').textContent = ''; clearLocation(); renderMasters();
  lock('Device data cleared. Sign in and sync again to prepare for offline work.');
});
async function boot() {
  if (booting) return; booting = true;
  try {
    // Online verification always takes precedence over the offline owner pointer.
    let identity;
    try { const ctx = await api('context'); identity = ctx.user; csrf = ctx.csrf_token; if (ctx.version !== 1 || !identity || !csrf) throw new ApiError('Unsupported server sync contract', 409); }
    catch(error) {
      if (error.status && error.status < 500 && ![408, 429].includes(error.status)) { lock('Sign in to ERPNext with a Field Agent or Field Manager account.'); tell(error.message, true); return; }
      identity = localStorage.getItem(ownerKey);
      if (!identity) { lock('This device needs an online sign-in and initial sync before offline capture.'); return; }
      tell('Using this account’s device storage offline. Pending records will sync after you sign in again.');
    }
    if (store) store.close(); user = identity; store = await openStore(user); localStorage.setItem(ownerKey, user);
    snapshot = await store.getMeta('references') || {customers: [], items: []};
    $('#identity').textContent = user; renderMasters(); if (!$('#order-lines').children.length) addLine(); await render(); unlock();
    if (navigator.storage?.persist) await navigator.storage.persist().catch(() => false);
    if (csrf) void sync();
  } catch(error) { lock('Device storage is unavailable. Enable browser storage and try again.'); tell(error.message, true); }
  finally { booting = false; connection(); }
}
window.addEventListener('online', () => { connection(); if (locked) void boot(); else void sync(); });
window.addEventListener('offline', connection);
window.addEventListener('focus', () => { if (navigator.onLine && !locked) void sync(); });
setInterval(() => { if (navigator.onLine && !locked) void sync(); }, 60000);
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('./sw.js', {scope: './', updateViaCache: 'none'}).then(() => navigator.serviceWorker.ready).then(() => {
    $('#offline-ready').textContent = 'Offline app shell installed. Complete a sync before your first offline trip.';
  }).catch(error => { $('#offline-ready').textContent = 'Offline app shell is unavailable.'; tell(`Offline app shell could not be installed: ${error.message}`, true); });
} else $('#offline-ready').textContent = 'This browser cannot install the offline app shell. Use a browser with service worker support over HTTPS.';
void boot();
