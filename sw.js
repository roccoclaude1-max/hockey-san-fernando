const CACHE = 'hockey-csf-v2';
const STATIC = [
  '/hockey-san-fernando/',
  '/hockey-san-fernando/index.html',
  '/hockey-san-fernando/manifest.json',
  '/hockey-san-fernando/icon.svg',
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)).catch(()=>{}));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.endsWith('datos.json')) {
    e.respondWith(
      fetch(e.request)
        .then(res => { const c=res.clone(); caches.open(CACHE).then(cc=>cc.put(e.request,c)); return res; })
        .catch(() => caches.match(e.request))
    );
    return;
  }
  e.respondWith(
    caches.match(e.request).then(r => {
      if (r) return r;
      return fetch(e.request).then(res => {
        if (res.ok) { const c=res.clone(); caches.open(CACHE).then(cc=>cc.put(e.request,c)); }
        return res;
      });
    })
  );
});
