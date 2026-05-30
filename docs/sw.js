// CLAIRVOYANCE ENGINE — Service Worker v2.2
const CACHE = 'cv-engine-v4';
const CORE = [
  './',
  './index.html',
  './config.js',
  './manifest.json',
  './clairvoyance-logo.svg',
  './icon-1080.png'
];
// Data files: always try network first so picks/live data stays fresh
const DATA_PATHS = ['data.json', 'live_data.json', 'social_copy.json'];

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
  const isData = DATA_PATHS.some(p => url.pathname.endsWith(p));
  const isExternal = url.origin !== location.origin;

  // External requests (APIs, fonts, ESPN): network-only, silent fail
  if (isExternal || isData) {
    e.respondWith(
      fetch(e.request)
        .then(r => {
          // Cache successful data responses for offline fallback
          if (r.ok && isData) {
            const clone = r.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone));
          }
          return r;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // App shell: cache-first, background revalidate
  e.respondWith(
    caches.match(e.request).then(cached => {
      const networkFetch = fetch(e.request).then(r => {
        if (r.ok) {
          const clone = r.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return r;
      }).catch(() => cached);
      return cached || networkFetch;
    })
  );
});
