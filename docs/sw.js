// SW SELF-DESTRUCT — clears all caches, unregisters itself, forces fresh reload
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.map(k => caches.delete(k))))
      .then(() => self.clients.claim())
      .then(() => self.registration.unregister())
      .then(() => self.clients.matchAll({type:'window',includeUncontrolled:true}))
      .then(clients => clients.forEach(c => { try{c.navigate(c.url);}catch(e){} }))
  );
});
// Pass every request straight through — no caching at all
self.addEventListener('fetch', e => e.respondWith(fetch(e.request).catch(() => new Response('', {status:503}))));
