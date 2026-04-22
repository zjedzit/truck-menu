// Service Worker dla Elvis POS — cache obrazków menu
// Wersja cache — zmień by wymusić odświeżenie u klientów
const CACHE_NAME = 'elvis-images-v1';
const IMAGE_PATTERN = /\/static\/images\//;

// Przy instalacji — pre-cache nic (lazy caching przy pierwszym fetch)
self.addEventListener('install', event => {
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    // Usuń stare wersje cache
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(k => k.startsWith('elvis-images-') && k !== CACHE_NAME)
                    .map(k => caches.delete(k))
            )
        ).then(() => self.clients.claim())
    );
});

// Strategia: Cache First dla obrazków, Network First dla reszty
self.addEventListener('fetch', event => {
    const url = event.request.url;

    if (IMAGE_PATTERN.test(url)) {
        // CACHE FIRST dla obrazków menu
        event.respondWith(
            caches.open(CACHE_NAME).then(cache =>
                cache.match(event.request).then(cached => {
                    if (cached) return cached;
                    // Nie ma w cache — pobierz z sieci i zapisz
                    return fetch(event.request).then(response => {
                        if (response.ok) {
                            cache.put(event.request, response.clone());
                        }
                        return response;
                    }).catch(() => cached); // offline fallback
                })
            )
        );
    }
    // Wszystkie inne requesty — normalna sieć (bez ingerencji)
});
