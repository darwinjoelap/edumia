{% load static %}
// Service worker de Edumia. PWA nivel 1 (D-22): instalabilidad y un "shell"
// mínimo en caché para que la app cargue algo (y una pantalla de aviso) sin
// conexión. PWA nivel 2 / Fase 7 (D-27): la cola offline (IndexedDB) y el
// reenvío con Background Sync — ver offline-sync-core.js, cargado aquí con
// importScripts porque este archivo corre en el hilo del service worker,
// no en el de la página.

importScripts("{% static 'js/offline-sync-core.js' %}");

const CACHE_NAME = "edumia-shell-v2";
const OFFLINE_URL = "{% url 'core:sin_conexion' %}";
const ARCHIVOS_SHELL = [
  "{% static 'css/edumia.css' %}",
  "{% static 'img/logo.png' %}",
  "{% static 'img/favicon-32.png' %}",
  "{% static 'js/offline-sync-core.js' %}",
  "{% static 'js/offline-status.js' %}",
  "{% static 'js/offline-forms.js' %}",
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

// --- Fase 7 (D-27): Background Sync de la cola offline --------------------
// `offline-forms.js` registra el tag "sync-aportes"/"sync-gastos" (en la
// página) apenas guarda algo en IndexedDB mientras no hay conexión. El
// navegador dispara este evento solo (incluso con la app cerrada, en
// Android/Chrome) en cuanto detecta que volvió la señal.

self.addEventListener("sync", (event) => {
  if (event.tag === "sync-aportes" || event.tag === "sync-gastos") {
    const tipo = event.tag === "sync-aportes" ? "aportes" : "gastos";
    event.waitUntil(self.EdumiaOffline.sincronizarCola(tipo).then(avisarClientes));
  }
});

function avisarClientes() {
  return self.clients.matchAll().then((clientes) => {
    clientes.forEach((cliente) => cliente.postMessage({ tipo: "edumia-offline-sync" }));
  });
}
