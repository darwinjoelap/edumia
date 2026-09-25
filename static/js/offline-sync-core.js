// offline-sync-core.js — Núcleo de la cola offline (Fase 7, D-27).
//
// Se carga tal cual (sin type="module") tanto en las páginas normales como
// en el service worker (con importScripts), por eso no usa import/export ni
// depende del DOM: solo IndexedDB y fetch, colgado de `self`/`window`.
(function (global) {
  "use strict";

  const DB_NOMBRE = "edumia-offline";
  const DB_VERSION = 1;
  const ALMACENES = { aportes: "cola_aportes", gastos: "cola_gastos" };
  const URLS_SYNC = { aportes: "/sync/api/aporte/", gastos: "/sync/api/gasto/" };

  function abrirDB() {
    return new Promise((resolve, reject) => {
      if (!("indexedDB" in global)) {
        reject(new Error("IndexedDB no disponible en este navegador."));
        return;
      }
      const solicitud = indexedDB.open(DB_NOMBRE, DB_VERSION);
      solicitud.onupgradeneeded = () => {
        const db = solicitud.result;
        Object.values(ALMACENES).forEach((almacen) => {
          if (!db.objectStoreNames.contains(almacen)) {
            db.createObjectStore(almacen, { keyPath: "uuid_cliente" });
          }
        });
      };
      solicitud.onsuccess = () => resolve(solicitud.result);
      solicitud.onerror = () => reject(solicitud.error);
    });
  }

  async function agregarPendiente(tipo, datos) {
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(ALMACENES[tipo], "readwrite");
      tx.objectStore(ALMACENES[tipo]).put({
        ...datos,
        _guardado_en: new Date().toISOString(),
        _estado: "pendiente",
        _error: null,
      });
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async function listarPendientes(tipo) {
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(ALMACENES[tipo], "readonly");
      const solicitud = tx.objectStore(ALMACENES[tipo]).getAll();
      solicitud.onsuccess = () => resolve(solicitud.result);
      solicitud.onerror = () => reject(solicitud.error);
    });
  }

  async function eliminarPendiente(tipo, uuidCliente) {
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(ALMACENES[tipo], "readwrite");
      tx.objectStore(ALMACENES[tipo]).delete(uuidCliente);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  async function marcarError(tipo, uuidCliente, mensaje) {
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(ALMACENES[tipo], "readwrite");
      const almacen = tx.objectStore(ALMACENES[tipo]);
      const solicitud = almacen.get(uuidCliente);
      solicitud.onsuccess = () => {
        const registro = solicitud.result;
        if (registro) {
          registro._estado = "error";
          registro._error = mensaje;
          almacen.put(registro);
        }
      };
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  function leerCookie(nombre) {
    if (typeof document === "undefined") return null;
    const partes = `; ${document.cookie}`.split(`; ${nombre}=`);
    if (partes.length === 2) return partes.pop().split(";").shift();
    return null;
  }

  // Envía un pendiente al servidor. Resultado:
  //  "ok"           — se creó o ya existía (idempotente, D-27): se borra de la cola.
  //  "error"        — el servidor lo rechazó (datos inválidos/permiso): se
  //                   marca como error, no se reintenta solo.
  //  "sin_conexion" — no hubo respuesta (red caída): se deja pendiente tal cual.
  async function enviarUno(tipo, registro) {
    const { _guardado_en, _estado, _error, ...payload } = registro;
    let respuesta;
    try {
      respuesta = await fetch(URLS_SYNC[tipo], {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": leerCookie("csrftoken") || "" },
        credentials: "same-origin",
        body: JSON.stringify(payload),
      });
    } catch (error) {
      return "sin_conexion";
    }
    if (respuesta.status === 200 || respuesta.status === 201) {
      await eliminarPendiente(tipo, registro.uuid_cliente);
      return "ok";
    }
    let detalle = `El servidor rechazó el envío (${respuesta.status}).`;
    try {
      const cuerpo = await respuesta.json();
      detalle = cuerpo.detalle || detalle;
    } catch (error) {
      /* respuesta sin JSON: se usa el detalle genérico de arriba */
    }
    await marcarError(tipo, registro.uuid_cliente, detalle);
    return "error";
  }

  // Recorre la cola de `tipo` e intenta enviar cada pendiente (los ya
  // marcados «error» se saltan: esperan que alguien los revise a mano, ver
  // el encabezado de sync/views.py). Si uno falla por falta de red, se
  // detiene ahí — los siguientes tampoco van a tener suerte ahora mismo.
  async function sincronizarCola(tipo) {
    let pendientes;
    try {
      pendientes = (await listarPendientes(tipo)).filter((r) => r._estado !== "error");
    } catch (error) {
      return 0;
    }
    let enviados = 0;
    for (const registro of pendientes) {
      const resultado = await enviarUno(tipo, registro);
      if (resultado === "ok") {
        enviados += 1;
      } else if (resultado === "sin_conexion") {
        break;
      }
    }
    return enviados;
  }

  async function contarPendientes() {
    try {
      const [aportes, gastos] = await Promise.all([listarPendientes("aportes"), listarPendientes("gastos")]);
      return aportes.length + gastos.length;
    } catch (error) {
      return 0;
    }
  }

  global.EdumiaOffline = {
    ALMACENES,
    abrirDB,
    agregarPendiente,
    listarPendientes,
    eliminarPendiente,
    marcarError,
    sincronizarCola,
    contarPendientes,
  };
})(typeof self !== "undefined" ? self : this);
