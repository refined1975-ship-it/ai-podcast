const CACHE_NAME = 'ai-news-v3';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  // MP3: only serve from cache (downloaded manually), never auto-cache
  if (event.request.url.endsWith('.mp3')) {
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request))
    );
    return;
  }

  // Other resources: network first, fall back to cache (for offline)
  event.respondWith(
    fetch(event.request).then(response => {
      const clone = response.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
      return response;
    }).catch(() => caches.match(event.request))
  );
});

// Listen for messages from the page to cache MP3s on demand
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'CACHE_MP3') {
    const url = event.data.url;
    caches.open(CACHE_NAME).then(cache => {
      cache.match(url).then(existing => {
        if (existing) {
          event.source.postMessage({ type: 'CACHE_DONE', url });
          return;
        }
        fetch(url).then(response => {
          cache.put(url, response).then(() => {
            event.source.postMessage({ type: 'CACHE_DONE', url });
          });
        }).catch(() => {
          event.source.postMessage({ type: 'CACHE_ERROR', url });
        });
      });
    });
  }

  if (event.data && event.data.type === 'DELETE_CACHE') {
    caches.open(CACHE_NAME).then(cache => {
      cache.delete(event.data.url);
    });
  }
});
