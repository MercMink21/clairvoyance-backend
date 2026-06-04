// CLAIRVOYANCE ENGINE — Service Worker v2.5
const CACHE = 'cv-engine-v9';
const CORE = [
  './config.js',
  './manifest.json',
  './clairvoyance-logo.svg',
  './icon-1080.png'
];
// Always fetch fresh from network (never cache HTML or data)
const NETWORK_FIRST = ['app.html', 'index.html', 'data.json', 'live_data.json', 'social_copy.json'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(CORE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  const isNetworkFirst = NETWORK_FIRST.some(p => url.pathname.endsWith(p)) || url.pathname === '/clairvoyance-backend/' || url.pathname === '/clairvoyance-backend';
  const isExternal = url.origin !== location.origin;

  // External (fonts, APIs) + HTML + data: network-first, cache fallback
  if (isExternal || isNetworkFirst) {
    e.respondWith(
      fetch(e.request)
        .then(r => {
          if (r.ok && !isExternal) {
            caches.open(CACHE).then(c => c.put(e.request, r.clone()));
          }
          return r;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Static assets (JS helpers, icons): cache-first, background revalidate
  e.respondWith(
    caches.match(e.request).then(cached => {
      const fresh = fetch(e.request).then(r => {
        if (r.ok) caches.open(CACHE).then(c => c.put(e.request, r.clone()));
        return r;
      }).catch(() => cached);
      return cached || fresh;
    })
  );
});
