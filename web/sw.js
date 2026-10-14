// Service worker: ljuska aplikacije radi i na lošem sajamskom Wi-Fiju.
// /api/ se NIKAD ne kešira — čitanje i slanje moraju ići na poslužitelj ili javno pasti.
const VERZIJA = 'sajam-v1'
const LJUSKA = [
  './', 'index.html', 'stil.css', 'app.js', 'manifest.webmanifest',
  'ikone/ikona-192.png', 'ikone/ikona-512.png', 'ikone/apple-touch.png',
]

self.addEventListener('install', (dogadaj) => {
  dogadaj.waitUntil(caches.open(VERZIJA).then((spremnik) => spremnik.addAll(LJUSKA)))
  self.skipWaiting()
})

self.addEventListener('activate', (dogadaj) => {
  dogadaj.waitUntil(
    caches.keys()
      .then((kljucevi) => Promise.all(kljucevi.filter((k) => k !== VERZIJA).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

// Mreža prva, spremnik kao rezerva: nova verzija stiže čim ima veze, stara radi bez nje.
self.addEventListener('fetch', (dogadaj) => {
  const url = new URL(dogadaj.request.url)
  if (dogadaj.request.method !== 'GET' || url.pathname.includes('/api/')) return
  dogadaj.respondWith(
    fetch(dogadaj.request)
      .then((odgovor) => {
        if (odgovor.ok) {
          const kopija = odgovor.clone()
          caches.open(VERZIJA).then((spremnik) => spremnik.put(dogadaj.request, kopija))
        }
        return odgovor
      })
      .catch(() => caches.match(dogadaj.request).then((s) => s || caches.match('index.html'))),
  )
})
