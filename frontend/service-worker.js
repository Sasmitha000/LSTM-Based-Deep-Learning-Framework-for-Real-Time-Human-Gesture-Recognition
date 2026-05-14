const CACHE_NAME = 'signbridge-v17';
const OFFLINE_CACHE = 'signbridge-offline-v17';

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/detection.html',
  '/learning.html',
  '/api-docs.html',
  '/privacy.html',
  '/get-api-key.html',
  '/user-dashboard.html',
  '/css/style.css',
  '/js/main.js',
  '/js/detection.js',
  '/manifest.json'
];

const OFFLINE_PAGES = [
  '/learning.html',
  '/api-docs.html',
  '/privacy.html'
];

// Install event - cache static assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('SignBridge SW: Caching static assets');
      return cache.addAll(STATIC_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Activate event - clean old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(key => key !== CACHE_NAME && key !== OFFLINE_CACHE)
            .map(key => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Skip API calls and socket connections
  if (url.port === '5001' || url.pathname.includes('/socket.io')) return;

  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;

      return fetch(event.request).then(response => {
        if (!response || response.status !== 200) return response;

        const clone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        return response;
      }).catch(() => {
        // Offline fallback
        if (event.request.destination === 'document') {
          return caches.match('/index.html');
        }
      });
    })
  );
});
