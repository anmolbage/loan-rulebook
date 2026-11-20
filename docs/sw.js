// Offline cache: app shell + encrypted data. Network first, so new builds show up as soon as you're online.
const CACHE = "jrb-v5";
const FILES = ["./", "index.html", "data.enc", "search.enc", "manifest.webmanifest", "icon.svg"];
self.addEventListener("install", e => { self.skipWaiting(); e.waitUntil(caches.open(CACHE).then(c => c.addAll(FILES).catch(() => {}))); });
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", e => {
  if (e.request.method !== "GET" || new URL(e.request.url).origin !== location.origin) return;
  e.respondWith(fetch(e.request).then(r => { const cp = r.clone(); caches.open(CACHE).then(c => c.put(e.request, cp)); return r; })
    .catch(() => caches.match(e.request, {ignoreSearch: true})));
});
