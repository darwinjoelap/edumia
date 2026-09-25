// offline-forms.js — Intercepta "Registrar ingreso" y "Registrar gasto"
// cuando el navegador está sin conexión (Fase 7, D-27): en vez de perder lo
// capturado, se guarda en IndexedDB (offline-sync-core.js) y se envía solo
// cuando vuelva la señal. Con conexión, el formulario funciona exactamente
// igual que antes (POST normal, esta capa ni se activa).
(function () {
  "use strict";

  function leerFormularioAporte(form) {
    const datos = Object.fromEntries(new FormData(form).entries());
    delete datos.csrfmiddlewaretoken;
    delete datos.tipo_concepto; // solo es el radio del toggle catálogo/libre, no un campo del modelo.
    return datos;
  }

  function leerFormularioGasto(form) {
    const renglonesPorIndice = {};
    const cabecera = {};
    for (const [nombre, valor] of new FormData(form).entries()) {
      if (nombre === "csrfmiddlewaretoken") continue;
      const coincide = nombre.match(/^renglones-(\d+)-(.+)$/);
      if (coincide) {
        const [, indice, campo] = coincide;
        renglonesPorIndice[indice] = renglonesPorIndice[indice] || {};
        renglonesPorIndice[indice][campo] = valor;
      } else if (!nombre.startsWith("renglones-")) {
        cabecera[nombre] = valor;
      }
    }
    cabecera.renglones = Object.values(renglonesPorIndice).filter((renglon) => {
      if (renglon.DELETE) return false; // fila marcada "Quitar"
      return (renglon.producto || renglon.descripcion) && renglon.cantidad && renglon.precio_unitario;
    });
    return cabecera;
  }

  function mostrarYRecargar(mensaje) {
    try {
      sessionStorage.setItem("edumia_offline_msg", mensaje);
    } catch (error) {
      /* sin sessionStorage no se ve el aviso, pero la cola ya quedó guardada */
    }
    location.reload();
  }

  async function registrarSyncEnSegundoPlano(tag) {
    if (!("serviceWorker" in navigator)) return;
    try {
      const registro = await navigator.serviceWorker.ready;
      if (registro.sync) {
        await registro.sync.register(tag);
      }
    } catch (error) {
      // Background Sync no disponible (ej. iOS, ver P-06): no importa, la
      // cola igual se sincroniza al recargar o reconectar (offline-status.js).
    }
  }

  function manejarEnvioOffline(form, tipo, leerDatos, mensajeExito) {
    form.addEventListener("submit", function (evento) {
      if (navigator.onLine) return; // hay conexión: sigue el flujo normal del formulario.
      if (typeof form.reportValidity === "function" && !form.reportValidity()) return;

      evento.preventDefault();
      const datos = leerDatos(form);
      datos.uuid_cliente = (crypto.randomUUID && crypto.randomUUID()) || `${Date.now()}-${Math.random()}`;

      window.EdumiaOffline.agregarPendiente(tipo, datos)
        .then(() => registrarSyncEnSegundoPlano("sync-" + tipo))
        .then(() => mostrarYRecargar(mensajeExito))
        .catch(() => {
          alert(
            "No se pudo guardar sin conexión en este dispositivo (el navegador no lo permite). " +
            "Intenta de nuevo cuando tengas señal.",
          );
        });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!window.EdumiaOffline) return;

    const formAporte = document.querySelector('form[data-offline-tipo="aportes"]');
    if (formAporte) {
      manejarEnvioOffline(
        formAporte, "aportes", leerFormularioAporte,
        "Aporte guardado en este dispositivo. Se enviará solo en cuanto vuelva la conexión.",
      );
    }

    const formGasto = document.querySelector('form[data-offline-tipo="gastos"]');
    if (formGasto) {
      manejarEnvioOffline(
        formGasto, "gastos", leerFormularioGasto,
        "Gasto guardado en este dispositivo. Se enviará solo en cuanto vuelva la conexión.",
      );
    }
  });
})();
