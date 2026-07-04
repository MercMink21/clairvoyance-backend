// Service worker — version-tagged cache buster
// Clears ALL caches on every install/activate, then unregisters itself
// This prevents stale JS from ever blocking the app

const SW_VERSION = Date.now(); // changes on every deploy

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.map(k => caches.delete(k))))
      .then(() => {
        // Unregister ourselves so we don't interfere with future loads
        return self.registration.unregister();
      })
      .then(() => {
        // Tell all clients to reload to get fresh content
        return self.clients.matchAll({ type: 'window' });
      })
      .then(clients => {
        clients.forEach(client => {
          if (client.navigate) client.navigate(client.url);
        });
      })
      .catch(() => {})
  );
});

// Pass all fetch requests through without caching
self.addEventListener('fetch', (e) => {
  e.respondWith(
    fetch(e.request).catch(() => new Response('', { status: 503 }))
  );
});
