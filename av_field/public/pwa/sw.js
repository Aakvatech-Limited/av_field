/* Cache only this version's public shell. Never cache API responses or login pages. */
const CACHE = 'av-field-shell-16.0.0';
const ROOT = new URL('./', self.location.href);
const SHELL = ['index.html', 'style.css', 'app.js', 'db.js', 'sync.js', 'manifest.webmanifest', 'icon-192.png', 'icon-512.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL.map(path => new Request(new URL(path, ROOT).href, {cache: 'reload'})))));
  // Keep an existing app version running until its tabs close. Never interrupt saves.
});
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) if (name.startsWith('av-field-shell-') && name !== CACHE) await caches.delete(name);
    await self.clients.claim();
  })());
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== ROOT.origin || !url.pathname.startsWith(ROOT.pathname)) return;
  if (event.request.mode === 'navigate') {
    event.respondWith(caches.open(CACHE).then(cache => cache.match(new URL('index.html', ROOT).href)));
    return;
  }
  if (!SHELL.some(path => url.pathname === new URL(path, ROOT).pathname)) return;
  event.respondWith(caches.open(CACHE).then(async cache => (await cache.match(event.request)) || fetch(event.request)));
});
