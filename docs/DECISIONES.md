# Edumia — Registro de decisiones

Formato: una entrada por decisión. Estado: **Cerrada** o **Pendiente**.
Última actualización: 2026-09-25

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

## D-21 — Recibo pensado para compartirse como imagen, no solo para imprimir (Fase 4)
- Estado: Cerrada (2026-09-25)
- Origen: Darwin pidió explícitamente que el recibo sea "atractivo" y que se pueda compartir como imagen (ej. WhatsApp) para ahorrar papel, además de la impresión en media carta del diseño original.
- Un solo diseño (`recibos/templates/recibos/_recibo_card.html` + `static/css/recibo.css`) sirve para los tres destinos: pantalla, impresión (`@media print`, tamaño media carta 5.5"×8.5") y descarga como imagen — no hay una plantilla "bonita" y otra "para imprimir" por separado.
- La imagen se genera en el navegador (`html2canvas`, botón "Descargar como imagen"), no en el servidor: más simple de mantener y no depende de una librería de renderizado de imágenes en el backend. El QR de verificación se incrusta como `data:image/png;base64,...` (generado con `qrcode`/Pillow en el servidor) precisamente para que `html2canvas` lo capture sin problemas de CORS.
- El recibo público (`/recibos/verificar/<uuid>/`) usa el mismo diseño y también puede descargarse como imagen: quien recibe el enlace del QR puede guardarlo, no solo verlo.
- Nuevas dependencias en `requirements.txt`: `qrcode` y `pillow` (esta última solo la usa `qrcode` para generar el PNG).

## D-22 — Gastos: saldo acumulado entre períodos, sin traslados entre fondos (Fase 5)
- Estado: Cerrada (2026-09-25)
- Origen: `docs/MODELOS_gastos.md` dejaba G-7 y G-8 abiertas; se resolvieron con Darwin antes de construir la Fase 5 (resuelve también P-08 y P-09 de la tabla de pendientes).
- **G-7 (saldo entre períodos):** el saldo de un fondo es acumulado — lo que sobra en un período escolar sigue disponible en el siguiente, no se reinicia al cerrar el período. `gastos/services.py::saldo_fondo()` ya suma sin filtrar por período (salvo que se pida explícitamente con `hasta=`); los reportes por período (Fase 6) mostrarán "saldo anterior + ingresos − gastos" sobre esa misma base.
- **G-8 (traslados entre fondos):** no se implementa por ahora. No existe modelo `TransferenciaFondo`; si más adelante hace falta (ej. "General presta al Comedor"), se agrega como una fase aparte sin tocar lo ya construido.
- **G-1 a G-6** (ya aprobadas en el diseño) quedaron implementadas tal cual: `Fondo.responsable` no existe (la relación vive en `PerfilUsuario.fondo`); `Gasto` tiene una sola moneda y el total sale de sumar los renglones (`Gasto.recalcular()`), no de convertir el total; segregación de funciones al aprobar (`Gasto.transicionar()` bloquea que quien registró también apruebe, salvo `Institucion.permitir_autoaprobacion` o confirmación explícita por gasto); `Aporte.fondo`/`Gasto.fondo` nunca quedan nulos; `Producto.nombre_normalizado` evita duplicados por mayúsculas/acentos; los renglones de un gasto `registrado` se pueden agregar/editar/quitar libremente, y quedan congelados al aprobar.
- Aprobar un gasto que deja el saldo del fondo en negativo avisa y pide confirmación explícita (`saldo_negativo_confirmado`), no bloquea — mismo criterio que la desviación de montos en `Aporte`.
- El formset de renglones (`DetalleGastoFormSet`) usa HTMX para agregar filas sin recargar la página: cada clic en "Agregar renglón" trae una fila vacía más del servidor y actualiza el contador `TOTAL_FORMS` del formulario con un *out-of-band swap*.
- De paso se agregó una pantalla de catálogo para Bancos (`/ingresos/configuracion/bancos/`, ya existía el modelo y el admin de Django, pero no una pantalla propia de Edumia) — no estaba en el alcance original de esta fase, pero Darwin la pidió al notar que no tenía dónde agregar bancos fuera de `/admin/`.

## D-23 — Filtrado de gastos por "macro" (categoría) y concepto (producto) en un rango de fechas: es un filtro, no una entidad nueva (Fase 5/6)
- Estado: Cerrada (2026-09-25)
- Origen: Darwin pidió poder crear un "nombre macro" (ej. "Comedor Semanal del 01/09 al 07/09") al que se le añaden conceptos (tomate, cebolla, leche), para saber cuánto se gastó en un concepto o en el macro dentro de un rango de fechas.
- Confirmado con Darwin: esto **ya lo cubre el modelo actual**, sin cambios de esquema:
  - El "macro" = `CategoriaGasto` (ej. "Comedor"), que ya existe como catálogo.
  - El "concepto" = `Producto` (ej. "Tomate"), ya enlazado a una única `CategoriaGasto` (`Producto.categoria`) — se confirmó que un producto pertenece a una sola categoría, no varias.
  - El rango de fechas ("01/09 al 07/09") **no se guarda como registro propio**: es un filtro que se aplica sobre `Gasto.fecha` al momento de consultar, no una entidad tipo "lote" o "campaña" con nombre persistido.
- Consecuencia para Fase 6 (Reportes): la pantalla de reportes de gastos debe permitir filtrar por Categoría y/o Producto, cruzado con un rango de fechas (`Gasto.fecha` entre dos valores), sumando `DetalleGasto.subtotal_ves`/`subtotal_usd` de los renglones que calcen. Así "¿cuánto se gastó en tomate del 01/09 al 07/09?" y "¿cuánto se gastó en Comedor del 01/09 al 07/09?" son la misma consulta con distinto nivel de filtro (producto vs. categoría), sin necesidad de un modelo nuevo.
- No se implementa nada de código en esta entrada: es una decisión de diseño para cuando se construya Fase 6.

## D-24 — Alcance real de la Fase 6 (primer lote): no existían "los once reportes" documentados
- Estado: Cerrada (2026-09-25)
- Al empezar la Fase 6, `docs/ESTADO.md` mencionaba "los once reportes" pero no existe (ni existió) un `docs/MODELOS_reportes.md` con esa lista — no se encontró en ningún documento del proyecto. En vez de inventar once reportes a ciegas, se le preguntó a Darwin cuáles priorizar.
- Se construyeron los **cuatro que Darwin eligió** como prioritarios, con un motor de filtros compartido (`reportes/services.py`) reutilizable para los que falten:
  1. **Ingresos por estudiante/sección/grado**, filtrable por rango de fechas, grado y sección, con opción de incluir no verificados.
  2. **Gastos por categoría/producto** (ver D-23), filtrable por rango de fechas, fondo, categoría y producto.
  3. **Balance por fondo**: saldo actual (reutiliza `gastos.services.saldo_fondo()`, ya probado desde la Fase 5) + gráfico de evolución mensual (Chart.js vía CDN) de ingresos verificados vs. gastos aprobados.
  4. **Estado de cuenta por estudiante**: buscador + historial completo de aportes (excluye anulados) con total verificado.
- Los cuatro tienen exportación a Excel (`openpyxl`, ya estaba en `requirements.txt` desde antes — no fue necesario agregar dependencias nuevas) vía `?formato=xlsx` sobre la misma URL filtrada.
- **De paso, se conectó el balance real del dashboard** (hueco documentado desde la Fase 2): `core/views.py:inicio` ahora suma `gastos.services.saldo_fondo()` de todos los fondos en vez de mostrar `Bs. 0,00` fijo. Los dos montos (Bs. y USD) se suman cada uno por su lado, sin reconvertir uno al otro con la tasa de hoy (mismo criterio que D-02/`saldo_fondo()`) — la tasa vigente se sigue mostrando, pero solo como referencia junto al botón "Ver en USD".
- Acceso: mismos roles que ya veían el balance en el dashboard (`administrador`, `responsable_fondo`, `director`, `auditor`); el docente no entra. `responsable_fondo` tiene el filtro de fondo bloqueado a su propio fondo en los reportes de Gastos y Balance (mismo criterio que `GastoForm` desde la Fase 5), verificado que no se puede forzar por la URL.
- **Queda pendiente, explícitamente fuera de este primer lote** (ver `docs/ESTADO.md`, Fase 6): los reportes restantes que Darwin no marcó como prioritarios ahora, exportación a PDF con encabezado (Excel sí quedó listo), y una revisión de índices/N+1 dedicada más allá de las consultas ya agregadas con `.values()/.annotate()` que se usaron en este lote.
- Validado en sandbox: `manage.py check`, `makemigrations --check --dry-run` (sin cambios — esta app no tiene modelos propios), la suite existente (`cambio`+`ingresos`, 15 tests, verde) y un script de 25 verificaciones nuevas con el `Client` de pruebas cubriendo los cuatro reportes, sus filtros, la exportación a Excel (content-type correcto), el balance real del dashboard, el bloqueo de fondo para `responsable_fondo`, y que el docente reciba 403.

## D-25 — PDF "Relación de gastos institucionales", con el formato en papel de la institución
- Estado: Cerrada (2026-09-25)
- Origen: Darwin mandó una foto de un documento en papel que ya usaba la institución (encabezado con escudo/nombre, tabla de "Disponibilidad e Ingresos" y "Desglose de Egresos" con una columna por fondo) y pidió reproducir ese formato en PDF.
- Se agregó `reportlab==5.0.1` a `requirements.txt` (wheel puro Python, `py3-none-any` — sin dependencias binarias que compilar, a diferencia de `weasyprint`, que en Windows necesita GTK/Cairo/Pango instalados aparte; se descartó por eso).
- Nuevo documento en `/reportes/gastos/relacion-pdf/?formato=pdf` (`reportes/pdf.py`): encabezado con "República Bolivariana de Venezuela" / "Ministerio del Poder Popular para la Educación" / nombre de la institución (con el logo si existe `static/img/logo.png`), año escolar (período activo), rango de fechas, tabla de ingresos verificados agrupados por concepto con total, y el desglose de gastos aprobados en una columna por fondo (máximo 3 columnas por fila; si hay más fondos, se sigue en la fila de abajo).
- Los montos del PDF se formatean `1,234.56` (coma de miles, punto decimal) **a propósito**, distinto del formato es-VE (`1.234,56`) que usa el resto de Edumia — es para que el documento coincida exactamente con el que ya conocía la institución, no con la convención interna de la app.
- Filtrable por rango de fechas y por fondo (vacío = todos los fondos, cada uno en su columna); `responsable_fondo` tiene el fondo bloqueado al suyo, igual que en Balance y Gastos por categoría (D-24).
- Validado en sandbox con un caso que reproduce los números exactos de la foto de Darwin (Bs. 622,321.00 de total de ingresos) y extrayendo el texto del PDF generado (`pypdf`) para confirmar que trae el nombre de la institución, el título, los conceptos de ingreso, las columnas por fondo y los productos/descripciones — 18 verificaciones, todas en verde. También se renderizó a imagen (`pdftoppm`) para revisión visual antes de entregarlo.
- Sigue pendiente (no se hizo en este lote, ver `docs/ESTADO.md`): exportar a PDF los otros tres reportes de la Fase 6 (Ingresos por estudiante, Gastos por categoría, Balance) — Darwin pidió "los reportes" en plural, pero el ejemplo concreto que mandó era este documento de gastos, así que se priorizó ese primero.

## D-26 — Fase 6: PDF para los otros tres reportes + índices dedicados
- Estado: Cerrada (2026-09-25)
- Cierra lo que había quedado pendiente en D-24/D-25. Se agregó exportación a PDF (botón junto al de Excel) a los tres reportes que solo la tenían en pantalla:
  - **Ingresos por estudiante**: mismo PDF genérico (`reportes/pdf.py::construir_tabla_pdf()`, nueva función reutilizable) con la tabla y el total.
  - **Gastos por categoría/producto**: igual, con `construir_tabla_pdf()`.
  - **Balance por fondo**: PDF propio (`construir_balance_pdf()`) con el saldo de cada fondo y la tabla de evolución mensual (los mismos datos del gráfico Chart.js, aquí en tabla para que se pueda imprimir — no se intentó incrustar el gráfico como imagen, hubiera hecho falta una librería de gráficos server-side aparte).
  - La Relación de gastos institucionales (D-25) ya tenía su propio PDF; ahora comparte el encabezado institucional (`_encabezado_institucional()`) con los otros tres, refactorizado a una función común.
- **Revisión de índices** (pendiente que quedaba de D-24): se agregaron dos índices compuestos que antes no existían y que los reportes (y `saldo_fondo()`, ya en uso desde la Fase 5) consultan directamente: `Aporte` → `(fondo, estado, fecha_pago)`; `Gasto` → `(fondo, estado, fecha)`. Migraciones `ingresos/migrations/0003_...` y `gastos/migrations/0003_...`, solo agregan índice — no hay dato que migrar ni riesgo de romper algo existente.
- Validado en sandbox: `makemigrations --check --dry-run` limpio tras generar las dos migraciones nuevas, `migrate` aplicado sin errores, la suite existente (15 tests) sigue en verde, y un script de 18 verificaciones nuevas — los tres PDF nuevos (status, content-type, firma `%PDF`, contenido extraído con `pypdf` confirmando institución/datos/total) y que las pantallas normales (sin `?formato=`) sigan funcionando igual que antes.
- Con esto, los **cuatro reportes de la Fase 6 tienen tanto Excel como PDF**. Sigue pendiente, sin marcar por Darwin como prioritario: los reportes fuera de los cuatro elegidos en D-24 (se agregan reutilizando el mismo motor de filtros y los mismos helpers de PDF).

## D-27 — Fase 7: cola offline (nivel 2 de D-08), primer lote — Aporte y Gasto
- Estado: Cerrada (2026-09-25)
- Origen: siguiente fase del plan (D-08 la dejaba para la Fase 7). Se acotó el alcance con Darwin antes de construir: solo **Registrar aporte** y **Registrar gasto** capturan sin conexión (no la alta rápida de estudiantes ni el registro en lote por sección, que quedan para más adelante si hace falta); y se resolvió P-06 (dispositivos): **solo Android**, así que Background Sync nativo del navegador es la vía principal.
- **Arquitectura:**
  - Cola local en el navegador con **IndexedDB** (`static/js/offline-sync-core.js`, dos almacenes: `cola_aportes`/`cola_gastos`, clave = `uuid_cliente` generado con `crypto.randomUUID()`). Este archivo no depende del DOM a propósito: se carga igual en la página (`<script>` normal) y dentro del service worker (`importScripts`), para no duplicar la lógica de envío.
  - Nueva app `sync` (sin modelos, sin migración) con dos endpoints JSON: `POST /sync/api/aporte/` y `POST /sync/api/gasto/` (`sync/views.py`). Construyen el modelo directamente (no pasan por `AporteForm`/`GastoForm`, porque el payload es JSON, no un POST de formulario) pero aplican las mismas reglas: `full_clean()` del modelo, la restricción de fondo propio para `responsable_fondo` (mismo criterio que `GastoForm`, D-14), y el rol requerido (`ROLES_REGISTRO` ya existentes en `ingresos`/`gastos`).
  - **Idempotencia (I-5, ya prevista desde la Fase 3/5 con `Aporte.uuid_cliente`/`Gasto.uuid_cliente`):** cada endpoint busca primero por `uuid_cliente`; si ya existe, devuelve 200 sin crear nada. Esto es necesario porque Background Sync puede reintentar un envío cuya respuesta se perdió de vuelta (el servidor sí guardó, el navegador no se enteró) — sin esto, ese reintento crearía un duplicado.
  - **Errores de validación (fondo/proveedor inválido, monto en cero, documento duplicado, etc.) responden 422, nunca 500** — a propósito: la cola del cliente solo reintenta sola cuando NO hay respuesta del servidor (caída de red real). Un 4xx marca el pendiente como "error" en IndexedDB y deja de reintentarse solo, para que alguien lo revise a mano; si en vez de eso fuera un 500, Background Sync lo reintentaría indefinidamente sin que nadie note que nunca va a funcionar.
  - **Formularios** (`ingresos/aporte_form.html`, `gastos/gasto_form.html` solo al crear, no al editar): `static/js/offline-forms.js` intercepta el `submit` únicamente cuando `navigator.onLine === false` — con conexión el formulario sigue funcionando exactamente igual que antes (POST normal, validación de servidor con errores en pantalla). Sin conexión: guarda el `FormData` tal cual en IndexedDB (para Gasto, agrupa los renglones por su prefijo `renglones-N-...` del formset), pide `Background Sync` (`reg.sync.register("sync-aportes"|"sync-gastos")`, con `try/catch` porque no existe en todos los navegadores) y recarga la pantalla con un aviso.
  - **Service worker** (`core/templates/core/sw.js`, ahora `edumia-shell-v2`): escucha el evento `sync` y llama a `sincronizarCola()`; al terminar, avisa a las pestañas abiertas con `postMessage` para que actualicen el indicador sin que el usuario tenga que recargar.
  - **Sin depender solo de Background Sync** (`static/js/offline-status.js`, cargado en `base.html` para cualquier usuario autenticado): al abrir cualquier página y al detectar el evento `online` del navegador, intenta sincronizar las dos colas igual — así la app también sirve en un dispositivo donde Background Sync no esté disponible, sin necesidad de tocar nada.
  - **Indicador visual de pendientes**: botón en el topbar (`base.html`, visible para administrador/responsable_fondo/superusuario) que muestra cuántos quedan por enviar y, al tocarlo, fuerza un intento de sincronización inmediato.
- **Fuera de alcance de este lote, documentado a propósito:** la app debe haberse abierto con conexión al menos una vez para poder llenar el formulario sin conexión (el service worker no precachea las páginas dinámicas de captura, solo el shell estático) — se avisa con una nota en las dos pantallas. Editar un gasto ya existente no admite modo offline (solo crear uno nuevo). La alta rápida de estudiantes y el registro en lote por sección se dejan para una fase aparte si hace falta.
- Validado en sandbox: `manage.py check`, `makemigrations --check --dry-run` (sin cambios — `sync` no tiene modelos), `migrate` limpio, la suite existente (`cambio`+`ingresos`, 15 tests) sigue en verde, `collectstatic` recoge los tres archivos JS nuevos sin error, y un script de 33 verificaciones nuevas contra los dos endpoints con el `Client` de pruebas: creación válida de Aporte y de Gasto (con renglones y total calculado), reenvío del mismo `uuid_cliente` (200, no duplica), anónimo/docente sin permiso (403), datos inválidos y tasa inexistente (422, nunca 500), `responsable_fondo` bloqueado a su propio fondo aunque el payload lo fuerce, JSON malformado (400), y el documento duplicado por proveedor (G-1, Fase 5) respetado también por esta vía.
- No se agregó ninguna dependencia nueva a `requirements.txt` (todo con `json`/`uuid` de la librería estándar de Python y APIs nativas del navegador).

## D-28 — Fase 8: se conectó la bitácora de auditoría (existía desde la Fase 1, no registraba nada)
- Estado: Cerrada (2026-09-25)
- Origen: al revisar qué faltaba para producción (Fase 8), se encontró que `RegistroAuditoria` (modelo de la Fase 1, pensado para login, verificaciones, anulaciones, etc.) nunca tuvo nada que lo alimentara — ni una sola fila se creaba en ningún flujo real. La pantalla del admin de Django (`RegistroAuditoriaAdmin`, ya de solo lectura) llevaba desde la Fase 1 mostrando una tabla vacía.
- **Se agregó `core/auditoria.py::registrar(request, accion, ...)`**, un solo punto de entrada que crea la fila (usuario desde `request.user`, IP desde `X-Forwarded-For`/`REMOTE_ADDR` — Render hace de proxy, así que `REMOTE_ADDR` por sí solo sería la IP interna de Render, no la del usuario). Nunca se llama desde los modelos (`Aporte.transicionar()`, `Gasto.transicionar()`, etc. siguen sin saber nada de HTTP): se llama desde las vistas, justo después de que la operación real ya se hizo con éxito.
- **Eventos conectados:** login y login fallido (`core/signals.py`, señales de `django.contrib.auth`, la única razón para agregar `core/apps.py` con un `ready()` — antes `core` no tenía `AppConfig` propio); verificar/observar/anular un aporte y la emisión del recibo que sigue a la verificación (`ingresos/views.py`); aprobar/anular un gasto (`gastos/views.py`); cargar o corregir una tasa de cambio (`cambio/views.py`); activar o cerrar un período escolar (`core/views.py`). Se ampliaron los `Accion.choices` del modelo (`observar`, `aprobar`, `editar_tasa`, `activar_periodo`) porque los originales de la Fase 1 no cubrían todo lo que ya existe desde las Fases 3–6 — migración `core/migrations/0005_alter_registroauditoria_accion.py` (solo cambia los `choices`, sin tocar datos).
- **Nueva pantalla de solo lectura** en `/configuracion/bitacora/` (rol administrador; antes solo se podía ver desde `/admin/`, reservado al superusuario de Django) — filtra por tipo de evento y por texto libre (usuario, modelo, # de objeto, descripción), paginada de 40 en 40.
- Un error al escribir en la bitácora nunca rompe el flujo principal: `registrar()` silencia cualquier excepción a propósito (una auditoría que le impide a alguien verificar un aporte sería peor que no tener auditoría).
- Validado en sandbox: `manage.py check`, `migrate` con la migración nueva aplicada limpio, la suite existente (15 tests) sigue en verde, y un script de 20 verificaciones nuevas — cada uno de los ocho eventos (login, login fallido, verificar/observar/anular aporte, aprobar/anular gasto, cargar/editar tasa, activar/cerrar período) queda registrado de verdad con el usuario y los datos correctos, la pantalla nueva filtra bien y un rol sin permiso recibe 403, y el admin de Django sigue siendo de solo lectura.
- **Fuera de alcance:** no se agregó un evento para "editar" (los `UpdateView` de catálogos como Grado, Sección, Proveedor, etc. no quedan auditados individualmente) — la bitácora se enfocó en los eventos financieros y de acceso que pedía el diseño original, no en un audit log genérico de cada UPDATE; si hace falta más adelante, se agrega evento por evento igual que estos.

## D-29 — Fase 8: backup externo automático de Neon (GitHub Actions + Releases)
- Estado: Cerrada (2026-09-25)
- Origen: el plan gratuito de Neon no incluye backup administrado (ya estaba anotado como pendiente desde la Fase 0/`docs/ESTADO.md`).
- **`.github/workflows/backup-neon.yml`**: workflow programado (todos los días a las 07:00 UTC = 03:00 hora de Venezuela) que instala `pg_dump`, hace un dump completo (`-Fc`, formato comprimido/custom) de la rama `production` de Neon, y lo publica como un **GitHub Release** con el nombre `backup-AAAA-MM-DD` — un Release no expira nunca solo (a diferencia de un artefacto normal de GitHub Actions, que Github borra a los 90 días por defecto). Al final, un paso en Python borra los releases de backup con más de 30 días, para no acumular espacio indefinidamente (GitHub no cobra por esto en un repo normal, pero igual no tiene sentido guardar 5 años de dumps diarios).
- También se puede disparar a mano desde la pestaña "Actions" del repo (`workflow_dispatch`), sin esperar al cron, por ejemplo justo antes de un cambio grande.
- **Requiere que Darwin agregue un secreto en GitHub** (Settings → Secrets and variables → Actions → New repository secret): `NEON_DATABASE_URL_PRODUCTION`, la cadena de conexión de la rama `production` de Neon (con `sslmode=require`) — la misma que ya usa temporalmente desde PowerShell para tareas puntuales (D-18), pero guardada como secreto en vez de pegada en un archivo. Sin ese secreto, el workflow falla de inmediato con un mensaje claro (no falla en silencio).
- **Restaurar un backup** (documentado para cuando haga falta, no se automatizó a propósito — restaurar es una operación que uno quiere hacer a mano, con cuidado, no en un cron): descargar el `.dump` del Release, y `pg_restore --clean --if-exists --no-owner -d "<DATABASE_URL de destino>" archivo.dump` desde PowerShell local (con la VPN apagada, D-15). Nunca restaurar directo sobre `production` sin probar antes contra una rama de prueba de Neon.
- No se validó en sandbox (no hay forma de correr un workflow de GitHub Actions real desde aquí): se verificó que el YAML es válido y que el script de Python embebido compila sin errores. **Queda pendiente que Darwin agregue el secreto y dispare el workflow una vez a mano** (`workflow_dispatch`) para confirmar que el primer backup se genera correctamente antes de confiar en el cron diario.

## D-30 — Fase 8: pantalla de Usuarios (crear/editar cualquier rol, no solo docente)
- Estado: Cerrada (2026-09-25)
- Origen: no existía ninguna forma de dar de alta un usuario salvo `/admin/`, reservado al superusuario de Django desde la Fase 2 (D-?, `core/admin.py::_solo_superusuario`). El rol administrador de Edumia no podía crear ni un docente. Darwin pidió primero "un template para registrar docente" y enseguida amplió a "falta el de usuarios" — se construyó una sola pantalla en `/configuracion/usuarios/` que cubre los cinco roles (`administrador`, `docente`, `responsable_fondo`, `director`, `auditor`), no una pantalla aparte solo para docentes.
- **Contraseña inicial (decidido con Darwin):** el administrador la escribe él mismo al crear el usuario y se la entrega directo a la persona (WhatsApp, en papel, etc.) — no se manda por correo, porque en producción no hay SMTP configurado todavía (`EMAIL_BACKEND` sigue en consola). El campo `PerfilUsuario.debe_cambiar_clave` (existía desde la Fase 2) se pone en `True` al crear, así que el sistema exige cambiarla en el primer login sin que haga falta correo.
- **Piezas nuevas** (`core/forms.py`, `core/views.py`, `core/urls.py`): `UsuarioCreateForm`/`UsuarioUpdateForm`/`RestablecerClaveForm` — no son `ModelForm` porque cada uno abarca dos modelos (`User` + `PerfilUsuario`) y guardan ellos mismos, dentro de una `transaction.atomic()` armada por la vista. `UsuarioListView` (filtra por rol y texto), `usuario_crear`, `usuario_editar`, `usuario_restablecer_clave`, `usuario_toggle_activo` — las cuatro últimas como vistas de función (mismo patrón que `periodo_activar`/`seccion_toggle_activa`), todas con `@requiere_rol("administrador")`.
- El campo "Fondo" solo aparece (JS vanilla, mismo patrón que "concepto libre" de Fase 3) cuando el rol elegido es «Responsable de fondo»; el formulario también lo exige/limpia en el servidor, no solo en la pantalla.
- Un administrador no puede desactivarse a sí mismo desde esta pantalla (evita quedarse afuera sin querer). La lista solo muestra usuarios con `PerfilUsuario` — un superusuario técnico creado por `createsuperuser` sin perfil (el que usa `/admin/`) no aparece ni se puede tocar desde aquí.
- **Se amplió la bitácora de auditoría (D-28)** con cinco eventos nuevos: `crear_usuario`, `editar_usuario`, `restablecer_clave`, `activar_usuario`, `desactivar_usuario` — migración `core/migrations/0006_alter_registroauditoria_accion.py` (solo cambia los `choices`, igual que D-28).
- Validado en sandbox: `manage.py check`, `makemigrations --check --dry-run` limpio tras generar la migración 0006, `migrate` aplicado, la suite existente (15 tests) sigue en verde, y un script de 38 verificaciones nuevas con el `Client` de pruebas — crear cada rol, responsable de fondo sin fondo (rechazado), fondo se limpia solo si el rol no es responsable de fondo, usuario duplicado (rechazado), contraseña débil (rechazada por los validadores ya configurados en `AUTH_PASSWORD_VALIDATORS`), contraseñas que no coinciden (rechazadas), editar rol y desactivar, un usuario desactivado no puede loguearse, restablecer clave (vuelve a pedir cambio en el próximo login), nadie puede autodesactivarse, docente/anónimo sin permiso (403), y los cinco eventos nuevos quedando en la bitácora.

## D-31 — Fase 8: unidades de medida ampliadas + comando de limpieza de datos de prueba
- Estado: Cerrada (2026-09-25)
- **Unidades de medida:** Darwin pidió dejar cargado un catálogo que cubra "todo tipo de productos", no solo alimentos. `seed_datos_iniciales.py` pasó de 8 a 23 unidades (`Kg`, `g`, `Litro`, `ml`, `Unidad`, `Par`, `Docena`, `Bulto`, `Saco`, `Paquete`, `Caja`, `Resma`, `Rollo`, `Galón`, `m`, `m2`, `Frasco`, `Tubo`, `Bolsa`, `Kit`, `Hora`, `Servicio`, `Global`) — pensado para que además de alimentos (Kg, Litro) cubra limpieza (Bolsa, Galón), papelería/oficina (Resma, Caja), mantenimiento (Metro, Rollo, Tubo) y servicios que no tienen una cantidad física real (Hora de mano de obra, Servicio, Global para un monto sin desglose). Es idempotente como el resto del comando: correrlo de nuevo solo agrega las que falten, no duplica las que ya existen.
- **Limpieza de datos antes de la marcha de prueba con el instituto:** Darwin eligió, entre las opciones planteadas, borrar todos los datos de prueba y dejar solo lo necesario. Nuevo comando `core/management/commands/limpiar_datos_prueba.py`:
  - Borra: bitácora de auditoría, recibos, series de recibo, aportes, gastos (y sus renglones, en cascada), tasas de cambio, inscripciones, estudiantes (y sus vínculos con representantes, en cascada), representantes, y los usuarios de prueba (cualquiera con `PerfilUsuario` que no sea superusuario, ni esté en `--mantener-usuario`).
  - Conserva sin tocar: Institución, períodos escolares, grados, secciones (quedan vacías de estudiantes, con `docente_responsable` en null si el docente se borró — `SET_NULL`, no hace falta tocarlo a mano), y todos los catálogos (bancos, formas de pago, conceptos de ingreso, montos por concepto, categorías de gasto, productos, proveedores, unidades de medida, fondos).
  - El orden de borrado respeta las relaciones `PROTECT` del esquema (recibo antes que aporte, aporte/gasto antes que usuarios y tasas, inscripción antes que estudiante, estudiante antes que representante) — no es un `TRUNCATE` a lo bruto, es una secuencia pensada para no toparse con un `ProtectedError` a mitad de camino.
  - **Por defecto no borra nada**: sin el flag `--confirmar` solo muestra los conteos de lo que hay y de lo que se borraría. Con `--confirmar` borra de verdad, dentro de una única `transaction.atomic()` (si algo falla a mitad de camino, no queda nada a medio borrar). `--mantener-usuario=usuario1,usuario2` protege cuentas adicionales además de los superusuarios (que siempre se conservan).
  - Se corre igual que las demás tareas de base de datos que ya ha hecho Darwin (D-18): con `DATABASE_URL` apuntando a Neon `production` desde PowerShell local, nunca desde aquí — es un borrado real de datos, así que lo corre él mismo, con el flag `--confirmar` explícito, después de revisar el conteo que muestra la corrida sin ese flag.
- Validado en sandbox: `manage.py check`, `makemigrations --check --dry-run` sin cambios (el comando no toca modelos), `seed_datos_iniciales` confirmado con las 23 unidades nuevas, y (dentro del mismo script de 38 verificaciones de D-30) el comando probado sin `--confirmar` (no borra nada) y con `--confirmar` (borra usuarios/aportes/gastos de prueba, conserva superusuario, catálogos y estructura, y deja `docente_responsable` de una sección en null en vez de romper con un error de integridad).

## D-32 — Fase 8: saldo inicial de fondos (pantalla de Fondos)
- Estado: Cerrada (2026-09-25)
- Origen: Darwin pidió "buscar una forma para ajustar el estado inicial de los fondos" — hasta ahora `Fondo` no tenía ningún concepto de saldo inicial ni pantalla propia (solo se creaba desde `/admin/`, y `saldo_fondo()` (Fase 6) arrancaba siempre en cero, sumando solo aportes verificados menos gastos aprobados). No había manera de cargar lo que un fondo ya tenía en caja antes de empezar a usar Edumia.
- **Diseño:** dos campos nuevos en `Fondo`, `saldo_inicial_ves` y `saldo_inicial_usd` (`DecimalField`, igual precisión que el resto del sistema bimoneda — D-02), que se suman siempre en `saldo_fondo()` como punto de partida, sin importar el filtro `hasta` (no son un movimiento con fecha, es el arranque). Los dos son independientes — igual que en todo el resto del sistema, VES y USD nunca se convierten entre sí (D-02).
- **Deliberadamente NO se recalculan solos ni se tocan con un `Aporte`/`Gasto` ficticio para "cuadrar" el saldo** — si el saldo inicial estuvo mal cargado, se corrige editando el campo directamente desde la pantalla de Fondos, nunca fabricando un movimiento falso (eso ensuciaría la bitácora y los reportes de aportes/gastos con datos que no son reales).
- **Piezas nuevas** (`gastos/forms.py`, `gastos/views.py`, `gastos/urls.py`, `gastos/templates/gastos/`): `FondoForm` (`ModelForm`, campos `nombre`, `descripcion`, `saldo_inicial_ves`, `saldo_inicial_usd`, `activo` — deliberadamente sin `es_general`: solo hay un Fondo General, protegido por un `UniqueConstraint`, y cambiar cuál fondo es "el general" desde una pantalla de edición rutinaria es peligroso/confuso, se deja como algo que solo se toca desde `/admin/` si alguna vez hiciera falta). `FondoListView` (tabla con saldo inicial y saldo actual lado a lado), `FondoCreateView`, `FondoUpdateView` — las tres con `@requiere_rol("administrador")` (mismo patrón que Categorías/Productos/Proveedores de Fase 5).
- **Auditoría:** se amplió la bitácora (D-28) con `crear_fondo` y `ajustar_saldo_fondo` — migración `core/migrations/0007_alter_registroauditoria_accion.py` (solo cambia los `choices`). `ajustar_saldo_fondo` solo se registra cuando `saldo_inicial_ves` o `saldo_inicial_usd` realmente cambiaron (`form.changed_data`) — así renombrar un fondo o activarlo/desactivarlo no genera bitácora de "ajuste de saldo" sin sentido.
- **Detalle técnico de la implementación (`FondoUpdateView.form_valid`):** para comparar el saldo antes/después y decidir si hace falta el evento de bitácora, los valores "de antes" se leen con una consulta directa a la base de datos (`Fondo.objects.filter(pk=...).values_list(...)`), no desde `self.object` — Django ya aplica los datos nuevos del formulario a `self.object` durante `form.is_valid()` (dentro de `full_clean()`), antes de que se llegue a `form_valid()`, así que leer `self.object` ahí ya habría mostrado los valores nuevos, no los viejos.
- Migración de modelo: `gastos/migrations/0004_fondo_saldo_inicial_usd_fondo_saldo_inicial_ves.py` (agrega los dos campos, `default=0` para que los fondos ya existentes no queden con saldo nulo).
- Validado en sandbox: `manage.py check`, `makemigrations --check --dry-run` limpio tras generar las dos migraciones, `migrate` aplicado, la suite existente (15 tests) sigue en verde, y un script de 15 verificaciones nuevas: permisos (docente sin acceso, administrador con acceso), crear fondo sin saldo inicial (arranca en 0), crear fondo con saldo inicial (el caso que pidió Darwin: lo que ya tenía antes de Edumia), bitácora registra `crear_fondo`, editar el saldo inicial queda en bitácora como `ajustar_saldo_fondo`, editar sin tocar el saldo NO genera ese evento, y un aporte verificado se suma correctamente al saldo inicial (`saldo actual = saldo inicial + aporte verificado`, en sus dos equivalentes VES/USD).

## D-33 — Fase 8: borrar catálogos sin uso (Secciones, Períodos, Productos, Proveedores, Categorías de gasto, Unidades de medida, Conceptos de ingreso, Formas de pago, Bancos)
- Estado: Cerrada (2026-09-25)
- Origen: Darwin, limpiando datos de prueba antes de pasarle el sistema al instituto, notó que podía editar cualquier catálogo pero no borrarlo — "veo que todo se puede editar pero no borrar". `Grado` ya tenía un botón de Borrar desde antes (con un chequeo manual de que no tuviera secciones asociadas); el resto de los catálogos de Configuración no.
- **Alcance decidido con Darwin** (por `AskUserQuestion`): Secciones, Períodos escolares, Productos, Proveedores, Categorías de gasto, Unidades de medida, Conceptos de ingreso, Formas de pago y Bancos. Fondos quedó deliberadamente afuera: un fondo arrastra saldo inicial y saldo actual (D-32), borrar uno con movimientos reales no tiene un significado limpio como "borrar un catálogo sin uso" — se deja para si hace falta más adelante, con su propio diseño.
- **Diseño — un solo helper reutilizable en vez de repetir el chequeo por cada modelo** (`core/utils.py::eliminar_protegido`): todas las relaciones hacia estos catálogos ya usan `on_delete=PROTECT` en todo el sistema (nunca `CASCADE`) — así que `objeto.delete()` de por sí ya se niega a arrastrar en cascada datos reales (aportes, gastos, inscripciones...) si el catálogo está en uso; solo hacía falta capturar el `ProtectedError` que Django levanta en ese caso y mostrar un mensaje claro en vez de un error 500. El helper arma el mensaje listando qué modelos lo están usando (`error.protected_objects`), y si el borrado sí procede, un mensaje de éxito — las nueve vistas nuevas (`*_eliminar`, una por catálogo, `@requiere_rol("administrador")`, solo POST) son una línea cada una: `return eliminar_protegido(request, objeto, "app:lista")`.
- Si el catálogo está en uso, no se puede borrar — el mensaje de error le dice a Darwin que lo desactive en su lugar (todas estas pantallas ya tienen un toggle Activo/Inactivo desde antes) en vez de dejarlo intentar de nuevo sin explicación.
- **Período escolar tiene una regla extra** sobre el chequeo genérico: nunca se puede borrar el período activo, aunque no tenga nada asociado todavía (se exige activar otro primero) — evita quedarse sin período activo por accidente.
- El botón de Borrar en cada pantalla pide confirmación (`confirm()` de JavaScript) antes de enviar, mismo patrón que ya usaba Grado y que "Cerrar período".
- No se tocó ningún modelo (todas las relaciones ya eran `PROTECT` desde que se diseñaron) — no hizo falta ninguna migración nueva.
- Validado en sandbox: `manage.py check`, `makemigrations --check --dry-run` sin cambios, la suite existente (15 tests) sigue en verde, y un script de 22 verificaciones nuevas: permisos (docente sin acceso a borrar una sección → 403), cada uno de los 9 catálogos borrado sin uso (éxito) y con uso (bloqueado, sigue existiendo), el período activo (bloqueado) y un período con secciones (bloqueado), y dos casos de regresión confirmando que el borrado de Grado (ya existente) sigue funcionando igual.

---

## Pendientes (sin respuesta aún)

| # | Pregunta | Afecta a | Bloquea |
| --- | --- | --- | --- |
| P-03 | ¿Qué tasa es la oficial: BCV, paralela o la que fije el consejo directivo? | `TasaCambio.fuente`, reportes | Fase 2 |
| P-04 | ¿El saldo por fondo es contable (aporte amarrado a fondo) o solo informativo? | `ConceptoIngreso.fondo`, saldo | Fase 5 |
| P-05 | ¿Cuántos alumnos y secciones hay? | Pantalla de registro en lote vs. búsqueda | Fase 3 |
| P-07 | Confirmar con el administrador: D-06, D-07 y pago parcial (D-13) | Modelo `Aporte` / `MontoConcepto` | Fase 1 (no bloquea el modelo; sí el flujo de captura de Fase 3) |

**P-06 resuelto (2026-09-25, ver D-27):** solo Android por ahora. Si más adelante se suma un iPhone, hay que revisar `static/js/offline-forms.js`/`offline-status.js` (ya están pensados para no depender de Background Sync, así que debería funcionar igual, pero conviene probarlo en ese dispositivo antes de confiar en él).
