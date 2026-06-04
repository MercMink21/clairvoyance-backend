// CLAIRVOYANCE ENGINE — Service Worker v3.0
const CACHE = 'cv-v10';
// HTML files are NEVER cached — always fetch live from server
const NEVER_CACHE = ['app.html', 'index.html', '/clairvoyance-backend/', '/clairvoyance-backend'];
// Only cache static assets that rarely change
const CACHE_ASSETS = ['config.js', 'manifest.json', 'icon-1080.png', 'clairvoyance-logo.svg'];

self.addEventListener('install', e => {
  // Take over immediately — don't wait for old SW to finish
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(CACHE_ASSETS.map(a => './'+a).filter(Boolean)))
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    // Delete ALL old caches
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
      .then(() => {
        // Force all open tabs to reload so they get the fresh SW + fresh HTML
        return self.clients.matchAll({type:'window', includeUncontrolled:true}).then(clients => {
          clients.forEach(client => {
            try { client.navigate(client.url); } catch(e) {}
          });
        });
      })
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  const path = url.pathname;
  const isExternal = url.origin !== location.origin;

  // HTML pages: always network, no cache
  const isHTML = NEVER_CACHE.some(p => path.endsWith(p)) || path === '/' || e.request.mode === 'navigate';
  if (isHTML || isExternal) {
    e.respondWith(
      fetch(e.request, {cache: 'no-store'})
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Data files: network first, cache fallback
  const isData = ['data.json','live_data.json','social_copy.json'].some(d => path.endsWith(d));
  if (isData) {
    e.respondWith(
      fetch(e.request)
        .then(r => { if(r.ok){caches.open(CACHE).then(c=>c.put(e.request,r.clone()));} return r; })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // Static assets: cache first
  e.respondWith(
    caches.match(e.request).then(cached =>
      cached || fetch(e.request).then(r => {
        if(r.ok) caches.open(CACHE).then(c => c.put(e.request, r.clone()));
        return r;
      })
    )
  );
});
