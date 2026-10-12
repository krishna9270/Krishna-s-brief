// Pages from this site and the digest are fetched fresh when online (so app updates
// arrive), with the cached copy used offline. Fonts and icons are cache-first.
const CACHE = "brief-v3";
const SHELL = ["./", "index.html", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  const fresh = url.origin === location.origin && (e.request.mode === "navigate" || /(\/|\.html|\.json|\.webmanifest)$/.test(url.pathname));
  if (fresh) {
    e.respondWith(
      fetch(e.request)
        .then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); return res; })
        .catch(() => caches.match(e.request))
    );
    return;
  }
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((res) => {
      if (res.ok && (url.origin === location.origin || url.host.endsWith("gstatic.com") || url.host.endsWith("googleapis.com"))) {
        const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy));
      }
      return res;
    }))
  );
});
