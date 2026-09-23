{% load static %}
// Service worker de Edumia — PWA nivel 1 (D-22): solo instalabilidad y un
// "shell" mínimo en caché para que la app cargue algo (y una pantalla de
// aviso) sin conexión. La sincronización real de datos offline (colas
// IndexedDB, Background Sync) es la Fase 7, todavía no está aquí.

const CACHE_NAME = "edumia-shell-v1";
const OFFLINE_URL = "{% url 'core:sin_conexion' %}";
const ARCHIVOS_SHELL = [
  "{% static 'css/edumia.css' %}",
  "{% static 'img/logo.png' %}",
  "{% static 'img/favicon-32.png' %}",
  OFFLINE_URL,
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ARCHIVOS_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((nombres) =>
        Promise.all(nombres.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
      )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") {
    return;
  }

  // Páginas (navegación): red primero; si no hay conexión, muestra el
  // aviso de "sin conexión" en vez de dejar el error del navegador.
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE_URL)));
    return;
  }

  // Estáticos del shell: caché primero (ya no cambian entre despliegues
  // dentro de una misma sesión de caché) y red como respaldo.
  if (request.url.includes("/static/")) {
    event.respondWith(
      caches.match(request).then((cacheado) => cacheado || fetch(request))
    );
  }
});
