# Edumia — Registro de decisiones

Formato: una entrada por decisión. Estado: **Cerrada** o **Pendiente**.
Última actualización: 2026-09-22

## D-01 — Alcance: una sola institución
- Estado: Cerrada
- Sin multi-tenant. `Institucion` es un singleton para el encabezado de recibos.

## D-02 — Bimoneda real con tasa congelada
- Estado: Cerrada, revisada 2026-09-25
- Cada transacción guarda `monto`, `moneda`, `tasa` (FK), `tasa_aplicada`, `monto_ves`, `monto_usd`.
- Montos y tasas: `DecimalField(max_digits=18, decimal_places=4)`. Nunca `FloatField`.
- Toda conversión pasa por `cambio/services.py` con `ROUND_HALF_UP`.
- Sin tasa para la fecha: se usa la última anterior y se avisa en pantalla; no se bloquea el registro.
- **Revisión (2026-09-25, pedido de Darwin):** `TasaCambio.valor` ya no es inmutable una vez que tiene aportes. Se puede editar para corregir una tasa mal cargada; al guardar, `TasaCambio.save()` recalcula en cascada los aportes que la usan y siguen en «registrado» u «observado». Los que ya están «verificado» o «anulado» no se recalculan (D-09 sigue protegiéndolos): si uno de esos quedó mal por una tasa errada, se anula y se registra de nuevo.

## D-03 — Stack
- Estado: Cerrada
- Django 5.x + PostgreSQL, plantillas server-side + HTMX. Sin SPA.
- Python **3.13** (decisión de Darwin, 2026-09-21; el plan original recomendaba 3.11/3.12 porque en Windows algunas ruedas binarias se compilan). Riesgo asumido: si alguna dependencia falla al instalar, se reevalúa e instala 3.12. Local y producción deben usar la misma versión (archivo `.python-version`). Confirmado sin problemas: `psycopg-binary` instaló como rueda precompilada tanto en Windows como en el build de Render.
- Django **5.2 LTS** (`django>=5.2,<6`). Sin fijar, `pip` instalaría Django 6.x.
- Settings divididos: `config/settings/{base,local,production}.py`.

## D-04 — Hosting: ~~Koyeb~~ Render (web) + Neon (Postgres)
- Estado: Cerrada, revisada en D-17 y D-18 (2026-09-22): Koyeb eliminó su plan gratuito para cuentas nuevas; se usa Render, que era el respaldo previsto desde el inicio.
- El código no depende del proveedor: todo por variables de entorno (`DATABASE_URL`, `SECRET_KEY`, `ALLOWED_HOSTS`), sin cambios de código al migrar. Confirmado en la práctica: el cambio de Koyeb a Render no requirió tocar ningún archivo de código, solo `config/settings/production.py` en sus comentarios.
- Neon gratis no da backups programados: respaldo propio desde Fase 0 (pendiente de implementar, ver Fase 8).
- Consecuencia aceptada: el servicio duerme tras ~15 min de inactividad; arranque en frío ~1 min. Mitigable con un ping externo cada 10 min (UptimeRobot / cron-job.org).
- **Desplegado y verificado:** https://edumia.onrender.com (2026-09-22).

## D-05 — Sin almacenamiento de archivos
- Estado: Cerrada
- Los datos del pago se transcriben como texto (referencia, bancos, teléfono, cédula del titular). No hay carpeta de media.

## D-06 — Aportes por estudiante
- Estado: Cerrada (2026-09-21); matizada por D-19 (2026-09-22)
- Cada `Aporte` cuelga de una `Inscripcion` **cuando el ingreso corresponde a un estudiante**. El recibo se emite a nombre de quien entregó (`entregado_por` / `entregado_por_nombre`).
- Caso "una madre, tres hijos, un solo pago": se registran tres aportes, uno por estudiante.
- Desde D-19: existen también ingresos sin estudiante asociado (rifas, donaciones), donde `inscripcion` queda vacío. Ver D-19 para el detalle.
- Riesgo asumido: si el administrador exige un pago único repartible, habrá que añadir un modelo `Pago` que agrupe aportes. Confirmar con el administrador antes de la Fase 3 (ver P-07).

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

## D-15 — Conexión a Neon requiere VPN apagada
- Estado: Cerrada (2026-09-22)
- La interfaz de VPN del equipo de Darwin (`ProTUN`) corta el handshake TLS hacia Neon (`server closed the connection unexpectedly`). Confirmado con `Test-NetConnection` (TCP abre bien) y resuelto al desactivar la VPN.
- Recordatorio permanente: desactivar la VPN antes de `migrate`, `runserver` con BD, `createsuperuser` contra Neon, o cualquier despliegue que hable con Neon. Se repitió una segunda vez (al crear el superusuario de producción), confirmando que es sistemático y no un evento aislado.

## D-16 — Ramas de Neon: `production` y `dev`
- Estado: Cerrada (2026-09-22)
- Neon creó por defecto la rama `production` (no `main`, como decía la guía original). `dev` cuelga de `production` como rama hija.
- `production` es la base de datos real, usada por Render; `dev` es la de la máquina local de Darwin. En el resto de los documentos, "rama main" debe leerse como "rama production".
- Superusuarios creados por separado en cada rama (son bases de datos distintas): uno en `dev` para desarrollo local, otro en `production` para el admin real.

## D-17 — Koyeb eliminó su plan gratuito para cuentas nuevas
- Estado: Cerrada (2026-09-22) — se cambia el hosting a Render
- Koyeb se unió a Mistral AI (anunciado ~feb-2026) y eliminó el plan "Starter" (gratuito) para cuentas nuevas. Confirmado en su propio blog: "New users will instead need to subscribe to the Pro, Scale, or Enterprise plan." Pro cuesta 29 USD/mes.
- La cuenta de Darwin en Koyeb se creó el 2026-09-22: es cuenta nueva, no tiene acceso al plan gratuito.
- Esto materializa el riesgo ya anotado en el plan original ("Koyeb cambia o recorta su capa gratuita"). El código es agnóstico del proveedor por diseño (D-03/D-04), así que cambiar de proveedor no implicó reescribir nada, solo redesplegar.
- Alternativa usada: **Render**, que mantiene su plan gratuito de servicio web en 2026 (duerme a los ~15 min de inactividad, arranque en frío de aproximadamente 1 min). Es el respaldo que el plan ya preveía.
- Implicación operativa: el docente que entra a las 7am puede esperar hasta un minuto la primera vez. Mitigación ya prevista en el plan original: ping externo cada 10 min con UptimeRobot o cron-job.org (pendiente de configurar, ver Fase 8 / ESTADO.md).
- Fuentes: [Koyeb is Joining Mistral AI](https://www.koyeb.com/blog/koyeb-is-joining-mistral-ai-to-build-the-future-of-ai-infrastructure), [Koyeb Pricing](https://www.koyeb.com/pricing), [Platforms with a real free tier for developers in 2026](https://render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026)

## D-18 — Render exige tarjeta incluso en el plan gratuito
- Estado: Cerrada (2026-09-22)
- Confirmado por Render Community (respuesta oficial): "We may prompt for card details for verification purposes - without entering a card you would be blocked from creating a service here." No es específico de la cuenta de Darwin, es política general.
- Es verificación de identidad, no una suscripción: autorización temporal de 1 USD que se libera sola. Mientras el servicio se quede dentro de los límites del plan Free, no hay cobro recurrente.
- Decisión de Darwin (2026-09-22): agregar la tarjeta y continuar con Render.
- Mitigación de riesgo: revisar de vez en cuando la sección "Billing → Unbilled charges" de Render para detectar cualquier consumo fuera del plan gratuito antes de que se facture. Pendiente como tarea recurrente (no automatizable, hay que entrar al dashboard).
- El plan Free de Render tampoco incluye **Shell** (terminal contra el contenedor en producción). Para tareas puntuales como `createsuperuser` en producción, se usa `DATABASE_URL` de `production` temporalmente desde la máquina local (variable de sesión de PowerShell, nunca en `.env`), con la VPN apagada (D-15).
- Fuente: [Render Community — Web service free tier credit card](https://community.render.com/t/web-service-free-tier-credit-card/33811)

## D-19 — `Aporte` puede existir sin estudiante (ingresos generales)
- Estado: Cerrada (2026-09-22)
- Origen: Darwin señaló que el sistema debe poder registrar ingresos por conceptos varios (rifas, donaciones) independientes de un estudiante — caso no cubierto por el diseño original de `ingresos`, donde `Aporte.inscripcion` era obligatoria.
- Ajuste a `MODELOS_cambio_ingresos.md`: `Aporte.inscripcion` pasa a ser opcional (`null=True`, sigue `PROTECT`). Cuando no hay inscripción, el aporte queda identificado por `concepto` y `entregado_por_nombre`.
- `Recibo`: las copias congeladas `estudiante_texto` y `seccion_texto` quedan vacías cuando no aplica; la plantilla impresa omite esas líneas en ese caso.
- La validación 9 de `Aporte` ("`inscripcion.estado` debe ser `activo`") solo aplica cuando hay inscripción.
- El reporte "Recaudación por concepto" no requiere cambios: ya no dependía de que hubiera estudiante.
- Detalle completo en `docs/MODELOS_cambio_ingresos.md`.

## D-20 — Alta rápida de estudiantes por sección, ya en la Fase 1
- Estado: Cerrada (2026-09-22)
- Origen: Darwin pidió que la carga de estudiantes pueda hacerla el docente de cada sección de forma manual, sin que sea una tarea pesada (no hay archivo Excel real de la escuela todavía).
- Se reutiliza el mismo patrón ya diseñado para el registro de aportes en lote (Fase 3): una vista de tabla por sección donde se agregan varias filas de una vez, en vez de un formulario Django estándar uno por uno.
- Se construye ya en la Fase 1, sin restricción de rol todavía (exige solo estar logueado como staff). En la Fase 2, cuando lleguen `PerfilUsuario` y los mixins de permisos (`SeccionDocenteMixin`, ya diseñado en `MODELOS_core_academico.md`), se agrega el filtro "solo mi sección" sin reescribir la vista.
- La importación desde Excel/CSV del plan original sigue construyéndose en la Fase 1 (formato genérico, con datos de prueba), pero deja de ser la única vía de carga masiva: la alta rápida por sección cubre el caso sin archivo.

---

## Pendientes (sin respuesta aún)

| # | Pregunta | Afecta a | Bloquea |
| --- | --- | --- | --- |
| P-03 | ¿Qué tasa es la oficial: BCV, paralela o la que fije el consejo directivo? | `TasaCambio.fuente`, reportes | Fase 2 |
| P-04 | ¿El saldo por fondo es contable (aporte amarrado a fondo) o solo informativo? | `ConceptoIngreso.fondo`, saldo | Fase 5 |
| P-05 | ¿Cuántos alumnos y secciones hay? | Pantalla de registro en lote vs. búsqueda | Fase 3 |
| P-06 | ¿Android, iPhone o mezcla en los docentes? | Background Sync (no existe en iOS) | Fase 7 |
| P-07 | Confirmar con el administrador: D-06, D-07 y pago parcial (D-13) | Modelo `Aporte` / `MontoConcepto` | Fase 1 (no bloquea el modelo; sí el flujo de captura de Fase 3) |
| P-08 | ¿El saldo sobrante de un fondo pasa al nuevo año escolar o se rinde y reinicia? (G-7; propuesta: acumulado) | `saldo_fondo`, reportes | Fase 5 |
| P-09 | ¿Se necesitan traslados entre fondos? (G-8; depende de P-04) | Modelo `TransferenciaFondo` | Fase 5 |
