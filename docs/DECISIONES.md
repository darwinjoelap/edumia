# Edumia — Registro de decisiones

Formato: una entrada por decisión. Estado: **Cerrada** o **Pendiente**.
Última actualización: 2026-09-21

## D-01 — Alcance: una sola institución
- Estado: Cerrada
- Sin multi-tenant. `Institucion` es un singleton para el encabezado de recibos.

## D-02 — Bimoneda real con tasa congelada
- Estado: Cerrada
- Cada transacción guarda `monto`, `moneda`, `tasa` (FK), `tasa_aplicada`, `monto_ves`, `monto_usd`.
- Montos y tasas: `DecimalField(max_digits=18, decimal_places=4)`. Nunca `FloatField`.
- Toda conversión pasa por `cambio/services.py` con `ROUND_HALF_UP`.
- Sin tasa para la fecha: se usa la última anterior y se avisa en pantalla; no se bloquea el registro.

## D-03 — Stack
- Estado: Cerrada
- Django 5.x + PostgreSQL, plantillas server-side + HTMX. Sin SPA.
- Python **3.13** (decisión de Darwin, 2026-09-21; el plan original recomendaba 3.11/3.12 porque en Windows algunas ruedas binarias se compilan). Riesgo asumido: si alguna dependencia falla al instalar, se reevalúa e instala 3.12. Local y producción deben usar la misma versión (archivo `.python-version`).
- Django **5.2 LTS** (`django>=5.2,<6`). Sin fijar, `pip` instalaría Django 6.x.
- Settings divididos: `config/settings/{base,local,production}.py`.

## D-04 — Hosting: Koyeb (web) + Neon (Postgres)
- Estado: Cerrada (a validar en Fase 0 midiendo arranque y latencia)
- Respaldo: Render. El código no depende del proveedor: todo por variables de entorno.
- Neon gratis no da backups programados: respaldo propio desde Fase 0.

## D-05 — Sin almacenamiento de archivos
- Estado: Cerrada
- Los datos del pago se transcriben como texto (referencia, bancos, teléfono, cédula del titular). No hay carpeta de media.

## D-06 — Aportes por estudiante
- Estado: Cerrada (2026-09-21)
- Cada `Aporte` cuelga de una `Inscripcion`. El recibo se emite a nombre de quien entregó (`entregado_por` / `entregado_por_nombre`).
- Caso "una madre, tres hijos, un solo pago": se registran tres aportes, uno por estudiante.
- Riesgo asumido: si el administrador exige un pago único repartible, habrá que añadir un modelo `Pago` que agrupe aportes. Confirmar con el administrador antes de la Fase 3.

## D-07 — Monto esperado varía por grado/nivel
- Estado: Cerrada (2026-09-21)
- Nuevo modelo `MontoConcepto`: `concepto` FK, `grado` FK, `periodo` FK, `monto`, `moneda`. Único por (concepto, grado, periodo).
- `ConceptoIngreso.monto_sugerido` queda como valor por defecto cuando no hay fila en `MontoConcepto`.
- La validación de desviación y el reporte de morosidad leen de `MontoConcepto`.

## D-08 — PWA en dos niveles
- Estado: Cerrada
- Nivel 1 (instalable + caché del shell): Fase 2.
- Nivel 2 (cola offline con IndexedDB, `uuid` de cliente, endpoint idempotente): Fase 7, aparte.

## D-09 — Inmutabilidad y anulación
- Estado: Cerrada
- Nada se borra. Aporte verificado / gasto aprobado no admite cambios de monto, fecha, moneda ni estudiante; solo anulación con motivo.
- Recibo anulado conserva su número. Numeración con `SerieRecibo` + `select_for_update()`.

## D-10 — Flujo de gastos
- Estado: Pendiente de confirmar
- Supuesto: el flujo docente registra → administrador verifica aplica solo a aportes. Los gastos los registra el responsable de fondo y el administrador los aprueba.

## D-11 — Cédulas nullable con unicidad condicional
- Estado: Cerrada (2026-09-21)
- `Estudiante.cedula_escolar` y `Representante.cedula` admiten null; únicas solo cuando tienen valor (`UniqueConstraint` con `condition=Q(campo__isnull=False)`).
- Motivo: niños de inicial y representantes sin documento a mano no deben bloquear la importación ni el registro.

## D-12 — Ubicación de `parentesco` y sección del docente
- Estado: Cerrada (2026-09-21)
- `parentesco` vive en `EstudianteRepresentante`, no en `Representante`.
- La sección de un docente se deriva de `Seccion.docente_responsable` en el período activo; `PerfilUsuario` no guarda sección.

## D-13 — Ajustes al modelo de ingresos
- Estado: Cerrada (2026-09-21)
- `ConceptoIngreso.periodicidad` (`unico`/`mensual`) y `Aporte.mes_cubierto` para poder calcular morosidad por mes.
- Se aceptan pagos parciales: el reporte de morosidad suma los aportes del mismo concepto y mes (a confirmar con el administrador, P-07).
- `TasaCambio` única por `(fecha, fuente)`.
- `FormaPago.requiere_banco_destino` como bandera adicional.
- `Aporte.uuid_cliente` desde la Fase 3 (idempotencia futura de la cola offline).
- `Recibo` guarda copia congelada de nombres (quien entregó, estudiante, sección, concepto, docente).
- `Aporte.fondo` se copia al registrar.
- Umbral de desviación de monto: ±20 %, configurable en `settings`.
- Detalle en `docs/MODELOS_cambio_ingresos.md`.

## D-14 — Ajustes al modelo de gastos
- Estado: Cerrada (2026-09-21)
- `Fondo.responsable` se elimina; la relación vive solo en `PerfilUsuario.fondo` (un fondo puede tener varios responsables).
- Un solo `moneda` por `Gasto`; el renglón no tiene `moneda_linea`. El total del gasto es la suma de renglones convertidos con la tasa de la cabecera.
- Segregación de funciones: quien registra un gasto no puede aprobarlo, salvo `Institucion.permitir_autoaprobacion` (falso por defecto).
- `Aporte.fondo` no nulo: sin fondo en el concepto, va al Fondo General (creado por migración de datos).
- `Producto.nombre_normalizado` único.
- Los renglones de un gasto `registrado` se pueden quitar; se congelan al aprobar.
- Detalle en `docs/MODELOS_gastos.md`.

---

## Pendientes (sin respuesta aún)

| # | Pregunta | Afecta a | Bloquea |
| --- | --- | --- | --- |
| P-03 | ¿Qué tasa es la oficial: BCV, paralela o la que fije el consejo directivo? | `TasaCambio.fuente`, reportes | Fase 2 |
| P-04 | ¿El saldo por fondo es contable (aporte amarrado a fondo) o solo informativo? | `ConceptoIngreso.fondo`, saldo | Fase 5 |
| P-05 | ¿Cuántos alumnos y secciones hay? | Pantalla de registro en lote vs. búsqueda | Fase 3 |
| P-06 | ¿Android, iPhone o mezcla en los docentes? | Background Sync (no existe en iOS) | Fase 7 |
| P-07 | Confirmar con el administrador: D-06, D-07 y pago parcial (D-13) | Modelo `Aporte` / `MontoConcepto` | Fase 1 |
| P-08 | ¿El saldo sobrante de un fondo pasa al nuevo año escolar o se rinde y reinicia? (G-7; propuesta: acumulado) | `saldo_fondo`, reportes | Fase 5 |
| P-09 | ¿Se necesitan traslados entre fondos? (G-8; depende de P-04) | Modelo `TransferenciaFondo` | Fase 5 |
