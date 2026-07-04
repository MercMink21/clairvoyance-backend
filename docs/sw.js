// Service worker — cache buster only, no forced reloads
// Clears ALL caches on install/activate, then unregisters itself
// Does NOT force clients to navigate (avoids reload loops)

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.map(k => caches.delete(k))))
      .then(() => self.registration.unregister())
      .catch(() => {})
  );
});

self.addEventListener('fetch', e => {
  e.respondWith(fetch(e.request).catch(() => new Response('', { status: 503 })));
});
