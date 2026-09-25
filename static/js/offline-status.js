// offline-status.js — Indicador de pendientes por sincronizar + intento de
// sincronización al abrir la app o al recuperar conexión (Fase 7, D-27).
// No depende de Background Sync (P-06: solo se confirmó Android por ahora):
// esto se ejecuta en cualquier navegador, así que la cola igual se vacía
// apenas alguien abre Edumia con señal, aunque Background Sync no exista.
(function () {
  "use strict";

  function mostrarMensajeGuardado() {
    let mensaje;
    try {
      mensaje = sessionStorage.getItem("edumia_offline_msg");
      if (mensaje) sessionStorage.removeItem("edumia_offline_msg");
    } catch (error) {
      return;
    }
    if (!mensaje) return;
    const contenedor = document.querySelector(".edumia-content, .edumia-guest-main");
    if (!contenedor) return;
    const aviso = document.createElement("div");
    aviso.className = "alert alert-warning shadow-sm";
    aviso.setAttribute("role", "alert");
    aviso.innerHTML = '<i class="bi bi-cloud-slash-fill me-1"></i> ' + mensaje;
    contenedor.prepend(aviso);
  }

  async function actualizarIndicador() {
    const boton = document.getElementById("edumia-offline-boton");
    const contador = document.getElementById("edumia-offline-contador");
    if (!boton || !contador || !window.EdumiaOffline) return;
    const total = await window.EdumiaOffline.contarPendientes();
    contador.textContent = total;
    boton.classList.toggle("d-none", total === 0);
    boton.classList.toggle("d-inline-flex", total > 0);
  }

  async function sincronizarSiHayConexion() {
    if (!navigator.onLine || !window.EdumiaOffline) return;
    await Promise.all([
      window.EdumiaOffline.sincronizarCola("aportes"),
      window.EdumiaOffline.sincronizarCola("gastos"),
    ]);
    actualizarIndicador();
  }

  document.addEventListener("DOMContentLoaded", function () {
    mostrarMensajeGuardado();
    if (!window.EdumiaOffline) return;
    actualizarIndicador();
    sincronizarSiHayConexion();

    const boton = document.getElementById("edumia-offline-boton");
    if (boton) {
      boton.addEventListener("click", function () {
        boton.disabled = true;
        sincronizarSiHayConexion().finally(() => {
          boton.disabled = false;
        });
      });
    }
  });

  window.addEventListener("online", sincronizarSiHayConexion);

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.addEventListener("message", function (evento) {
      if (evento.data && evento.data.tipo === "edumia-offline-sync") {
        actualizarIndicador();
      }
    });
  }
})();
