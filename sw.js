const CACHE_NAME = 'ai-news-v2';

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', () => self.clients.claim());

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        // Cache non-MP3 resources automatically
        if (!event.request.url.endsWith('.mp3')) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      });
    })
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
