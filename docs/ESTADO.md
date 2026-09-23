# Edumia — Estado del proyecto

Regla: no se empieza una fase sin cerrar la anterior aquí.
Última actualización: 2026-09-23

**Fase actual:** 2 — Usuarios, roles, tasa y PWA nivel 1 (sin empezar)
**MVP:** Fases 0–4 (92–126 h)

| Fase | Nombre | Horas | Estado |
| --- | --- | --- | --- |
| 0 | Infraestructura y hosting | 8–12 | **Cerrada** (hosting: Render, no Koyeb — D-17/D-18) |
| 1 | Núcleo académico | 20–28 | **Cerrada** (2026-09-22) |
| 2 | Usuarios, roles, tasa y PWA nivel 1 | 18–24 | Pendiente |
| 3 | Ingresos | 30–40 | Pendiente |
| 4 | Recibos | 16–22 | Pendiente |
| 5 | Gastos | 28–36 | Pendiente |
| 6 | Reportes y balance | 30–40 | Pendiente |
| 7 | PWA offline | 24–32 | Pendiente |
| 8 | Puesta en producción | 20–30 | Pendiente |

## Diseño (previo a la Fase 0)
- [x] Plan de desarrollo
- [x] `docs/DECISIONES.md` (D-01 a D-20, pendientes P-03 a P-09)
- [x] `docs/ESTADO.md`
- [x] Diseño detallado de modelos: `core` y `academico` (aprobado)
- [x] Diseño detallado de modelos: `cambio` (aprobado)
- [x] Diseño detallado de modelos: `ingresos`, incluye `MontoConcepto` (aprobado; revisado por D-19 — `Aporte` sin estudiante)
- [x] Diseño detallado de modelos: `gastos` (aprobado; G-7 y G-8 abiertas)
- [ ] Confirmar D-06 y D-07 con el administrador (P-07) — no bloquea el código, sí el flujo de captura de la Fase 3

## Fase 0 — Infraestructura — CERRADA (2026-09-22)
- [x] Verificar versión de Python del venv → 3.13 (D-03)
- [x] Repo local, venv, `requirements.txt`, `.env.example`, `.gitignore`
- [x] Esqueleto Django con settings base/local/production
- [x] Cuenta Neon creada. Ramas: `production` (base real, usada por Render) y `dev` (local)
- [x] Migraciones base aplicadas en Neon `dev`; superusuario local creado
- [x] Vista `/salud/` sin consultas a la BD, verificada en local
- [x] Admin verificado en local con las credenciales del superusuario
- [x] Repositorio en GitHub: https://github.com/darwinjoelap/edumia (rama `main`)
- [x] Cuenta en Render creada, tarjeta agregada para verificación (D-18; sin cobro mientras se use el plan Free)
- [x] Desplegado en Render: https://edumia.onrender.com — build y migraciones contra Neon `production` sin errores
- [x] HTTPS confirmado en el dominio de Render (lo da por defecto)
- [x] Migraciones aplicadas en Neon `production`; superusuario de producción creado (vía `DATABASE_URL` temporal desde local, D-18)
- [x] `/salud/` y `/admin/` verificados en producción (https://edumia.onrender.com)
- [x] Decisión de hosting validada en `DECISIONES.md` (D-04, D-17, D-18)

*Cierre: la app responde en una URL pública con Postgres conectado. — CERRADA 2026-09-22.*

### Pendientes que no bloquean, pero quedan abiertos de la Fase 0
- [ ] Configurar ping externo cada 10 min (UptimeRobot / cron-job.org) a `/salud/` para evitar que Render duerma el servicio. Se puede hacer ahora o esperar a la Fase 8; anotar si el arranque en frío molesta durante las pruebas.
- [ ] Revisar de vez en cuando "Billing → Unbilled charges" en Render (D-18), para confirmar que no haya cargos fuera del plan gratuito.
- [ ] Backup automatizado de Neon (Fase 8), ya que el plan gratuito no lo incluye.

## Fase 1 — Núcleo académico — CERRADA (2026-09-22)
- [x] Modelos `core`: `Institucion`, `PeriodoEscolar`, `RegistroAuditoria` + migración aplicada en `dev` local
- [x] Admin de `core` configurado (Institución como singleton, bitácora de solo lectura)
- [x] Modelos `academico`: `Grado`, `Seccion`, `Estudiante`, `Representante`, `EstudianteRepresentante`, `Inscripcion` + migración aplicada en `dev` local (incluye historial de `Estudiante`, `Representante`, `Inscripcion`)
- [x] Admin de `academico` configurado (inlines de inscripción y representantes en el estudiante)
- [x] Verificar admin en el navegador
- [ ] `PerfilUsuario` queda para la Fase 2 (no en esta fase, ver nota abajo); la validación de rol del docente en `Seccion.clean()` ya está escrita a prueba de esa ausencia
- [x] Datos iniciales: `Institucion` (ejemplo, editar en admin), `PeriodoEscolar` 2026-2027 activo, 14 `Grado` (Inicial, Primaria, Media) — comando `seed_datos_iniciales`, idempotente
- [x] Alta rápida de estudiantes por sección (D-20): vista de tabla en `/academico/secciones/<id>/alta-rapida/`, varias filas de una vez, filas vacías se ignoran, cédulas repetidas se validan; sin restricción de rol todavía (llega en Fase 2) — probado en el navegador
- [x] Importación de estudiantes desde Excel/CSV: vista web en dos pasos (`/academico/secciones/<id>/importar/`, subir → vista previa → confirmar), con o sin fila de encabezado; probado con un `.csv` real sin encabezado
- [x] CRUD de representantes: listar (con búsqueda y filtro activo/inactivo), crear, editar, activar/desactivar (D-09: sin borrado físico), y gestionar sus vínculos con estudiantes (`EstudianteRepresentante`) desde la ficha del representante
- [x] Bonus (no estaba en el checklist original, se agregó al pedirlo): CRUD de estudiantes — listar/ver/editar/activar-desactivar (con filtro por sección y nivel), la creación ya la cubren la alta rápida y la importación
- [x] Acción masiva de promoción al período siguiente: vista en dos pasos en `/academico/promocion/` (elegir período destino → vista previa por sección → confirmar); "siguiente grado" = `orden` inmediato superior en `Grado` (encadena Inicial→Primaria→Media solo); el último grado (5to Año) marca `egresado` en vez de promover; probado en el navegador
- [x] Migrado y verificado en Neon `production`: `migrate` aplicó `core.0001_initial` y `academico.0001_initial` sin errores; `seed_datos_iniciales` corrido también ahí (Institución de ejemplo, Período 2026-2027 activo, 14 Grados) — pendiente que edites la Institución con los datos reales de la escuela en el admin de producción antes de la Fase 4 (recibos)

*Cierre: el esquema y los catálogos base ya están en producción; la nómina real de la escuela se carga cuando la escuela la entregue, usando la alta rápida o la importación ya construidas — eso no bloquea seguir con la Fase 2. — CERRADA 2026-09-22.*

## Fase 2 — Usuarios, roles, tasa y PWA nivel 1
- [x] `PerfilUsuario` (rol, fondo solo para responsable_fondo, teléfono, debe_cambiar_clave), sincroniza automáticamente el `Group` de Django en `save()` — el rol es la única fuente de verdad, nunca se edita el Group directamente
- [x] Se adelantó `gastos.Fondo` desde la Fase 5 (solo ese modelo) porque `PerfilUsuario.fondo` necesita apuntar a algo; el Fondo General se crea desde `seed_datos_iniciales` (idempotente, no por migración de datos porque `gastos` no tenía migraciones aún)
- [x] Admin: `PerfilUsuario` como inline en el admin de `User` (`UserAdmin` personalizado); `FondoAdmin` con borrado bloqueado para el Fondo General (D-09)
- [x] `core/mixins.py`: `RolRequeridoMixin` (CBV), `requiere_rol(*roles)` (decorador), `verificar_seccion_docente(request, seccion)` — el superusuario siempre pasa, sin importar el rol
- [x] Todas las vistas de `academico` ahora requieren login (`@login_required` / `LoginRequiredMixin`); alta rápida e importación de estudiantes (Fase 1) restringidas a "solo mi sección" para el rol docente vía `verificar_seccion_docente`
- [x] Login, cambio y recuperación de contraseña: `django.contrib.auth.urls` en `/cuentas/`, plantillas propias en `templates/registration/` con el estilo de Edumia; `EMAIL_BACKEND` por defecto en consola (falta configurar SMTP real en producción para que el correo de recuperación llegue de verdad — ver Pendientes)
- [x] `TasaCambio` (fecha, valor, fuente, cargada_por), único `(fecha, fuente)`, `valor > 0`, índice `(fuente, -fecha)`, con historial (`simple_history`); admin con carga manual (`cargada_por` se fija sola al usuario que crea el registro)
- [x] `cambio/services.py`: `obtener_tasa(fecha, fuente=None)` (exacta o la última anterior, `SinTasaError` si no hay ninguna), `convertir(monto, moneda, tasa_valor)` (`ROUND_HALF_UP`, 4 decimales, la moneda de origen queda exacta), `formatear(monto, decimales=2)` (formato es-VE `1.234,56`)
- [x] Pruebas unitarias de `cambio/services.py`: redondeo en .5 exacto, tasa con 4 decimales, monto cero, ida y vuelta USD→VES→USD sin desviarse más de 0,0001, `SinTasaError`, formateo (con miles, sin decimales, negativos)
- [ ] `MontoBimonedaMixin` (lo heredan `Aporte` y `Gasto`) — se construye en la Fase 3/5, cuando existan esos modelos; no tiene sentido antes
- [x] Rediseño visual completo (adelantado, fuera del alcance original de la Fase 2 pero pedido explícitamente): sistema de diseño en `static/css/edumia.css` con la paleta tomada del logo (navy `#15467e`/`#0e3062`, teal `#1aa18a`, acento naranja `#f9b23b`); `base.html` reconstruido como shell de aplicación (sidebar con offcanvas responsive + topbar) para usuarios autenticados, y pantalla centrada con el logo para login/recuperación; dashboard nuevo en `/` (`core/templates/core/dashboard.html` + `core/views.py:inicio`, ahora con `@login_required`) con tarjetas de resumen (estudiantes activos, representantes activos, secciones, período activo), accesos rápidos y tabla de secciones del período; como las 11 plantillas de `academico` y las de `registration/` ya usaban las clases compartidas `card-edumia`/`btn-edumia-primary`, heredan el nuevo estilo sin reescribirse — solo se les agregó el título del topbar; logo guardado en `static/img/` (logo.png + favicon en dos tamaños) y añadido `STATICFILES_DIRS` + `STORAGES` (whitenoise `CompressedManifestStaticFilesStorage`) en `settings/base.py`
- [x] Panel de configuración para el rol `administrador` (adelantado, pedido explícitamente): nueva app de rutas `core/urls.py` en `/configuracion/`, protegida con `requiere_rol("administrador")`/`RolRequeridoMixin` (el superusuario también pasa); incluye edición de `Institucion` (singleton), CRUD de `Grado` (con bloqueo de borrado si tiene `Seccion` asociadas) y CRUD de `PeriodoEscolar` con acciones separadas "Activar" (desactiva el resto vía `transaction.atomic()`, respeta la restricción `un_solo_periodo_activo`) y "Cerrar" (marca `cerrado`, `cerrado_por`, `fecha_cierre`); nuevo `core/forms.py`
- [x] `/admin/` de Django restringido a superusuario (adelantado): `core/admin.py` sobreescribe `admin.site.has_permission` para exigir `is_superuser` (antes bastaba `is_staff`); el enlace al panel de Django en el sidebar y en el dashboard ahora depende de `user.is_superuser`, no de `user.is_staff`; el rol `administrador` usa `/configuracion/` en su lugar
- [x] Dashboard: sección de balance y accesos rápidos "Registrar ingreso" / "Registrar gasto" (adelantado, pedido explícitamente, sin funcionalidad real todavía porque `Aporte`/`Gasto` no existen hasta las Fases 3 y 5): tarjeta `balance-card` con `Bs. 0,00` (placeholder honesto, listo para calcularse cuando existan esos modelos) y dos botones grandes que enlazan a `core:proximamente` (pantalla "próximamente"); visible solo para roles que manejan dinero (`administrador`, `responsable_fondo`, `director`, `auditor`) — el docente no lo ve; nuevas clases CSS `.balance-card`/`.action-btn*` en `edumia.css`
- [x] CRUD de `Seccion` en `/configuracion/secciones/` (adelantado, pedido explícitamente — antes solo existía en el admin de Django, que ahora es exclusivo del superusuario): un grado puede tener varias secciones (ej. "1er grado" con A, B y C); formulario con `grado`, `periodo` (por defecto el activo), `nombre`, `docente_responsable` (limitado a usuarios con rol `docente`) y `activa`; listado filtrable por período (por defecto el activo); "eliminar" es desactivar (`activa=False`, D-09), igual que representantes/estudiantes; nuevo `core/templates/core/configuracion/seccion_lista.html` y `seccion_form.html`
- [x] Se quitó `Institucion.codigo_dea` (pedido explícitamente, ya no aplica) — migración `core/migrations/0003_remove_institucion_codigo_dea.py`, campo también removido de `InstitucionForm`
- [x] Promoción masiva con asignación manual de sección destino (implementado, reemplaza el emparejamiento automático por nombre): `academico/promocion.py` reescrito — `calcular_plan_manual()` agrupa por sección de origen con la lista de estudiantes activos, el grado siguiente y las secciones destino disponibles (sugiriendo, sin forzar, la de mismo nombre si existe); `ejecutar_promocion_manual(asignaciones)` aplica lo elegido, es idempotente (a quien ya tiene inscripción en el destino no se le vuelve a tocar) y no bloquea el lote si algunos quedan "sin destino" — se avisa cuántos y se puede volver a correr para completarlos. Paso 2 nuevo (`academico/templates/academico/promocion_asignar.html`): una tarjeta por sección de origen, un `<select>` de sección destino por estudiante (`name="destino_<id>"`, procesado directo del `POST` sin formset), botón "Aplicar a todos" por sección (JS vanilla, sin librerías) y aviso cuando el grado siguiente no tiene ninguna sección creada en el período destino (enlaza a Configuración → Secciones); las secciones sin grado siguiente muestran aviso de "egresa" sin selects. `promocion_form.html` actualizado (ya no menciona `/admin/` ni "mismo nombre" como regla).
- [x] PWA nivel 1 (instalabilidad + shell mínimo en caché, sin sincronización offline — eso es la Fase 7): `static/manifest.json` (nombre, colores del sistema de diseño, ícono 192 reusando el favicon existente y un `icon-512.png` nuevo generado a 512×512 desde el logo), service worker Django-renderizado en `core/templates/core/sw.js` servido en la **raíz** del sitio vía `core/views.py:service_worker` + `path("sw.js", ...)` en `config/urls.py` (deliberado: si se sirviera desde `/static/` el scope por defecto quedaría limitado a `/static/` en vez de cubrir todo el sitio) — cachea CSS, logo, favicon y la página de sin conexión al instalarse, estrategia network-first con fallback a caché para estáticos y a `core:sin_conexion` para navegación; `core/templates/core/sin_conexion.html` con botón "Reintentar"; `base.html` con `<link rel="manifest">`, `theme-color` y meta tags de Apple, más el registro del service worker en `<script>` al final del `<body>`
- [ ] Instalación verificada en Android y escritorio — **pendiente, requiere prueba manual tuya tras el despliegue**
- [x] Botón de cambio de moneda en el balance del dashboard (adelantado, pedido explícitamente): `core/views.py:inicio` obtiene la tasa de cambio vigente con `cambio.services.obtener_tasa()` (la de hoy, o la última anterior si no hay una exacta) y convierte el balance a USD con `convertir()`/`formatear()`; el botón solo aparece si hay alguna `TasaCambio` cargada — si no hay ninguna, se oculta y el balance se ve solo en Bs. como antes. En la tarjeta de balance, un botón "Ver en USD" (JS vanilla, sin librerías) alterna entre el monto en Bs. y en `$` sin recargar la página; debajo se indica la fuente y fecha de la tasa usada (y si es la última disponible en vez de la de hoy). Como el balance real todavía es 0 (Fase 3/5 pendientes), hoy solo alterna entre "Bs. 0,00" y "$ 0,00", pero ya queda listo para cuando haya montos reales.

### Pendiente de validar en el navegador / consola (este lote y los anteriores)
- [ ] `makemigrations core`, `makemigrations gastos`, `makemigrations cambio`, `migrate` en local; volver a correr `seed_datos_iniciales` (crea el Fondo General)
- [ ] `migrate` de `ingresos.0001_initial` contra tu Postgres real (Neon `dev`) y luego `seed_datos_iniciales` para cargar bancos y formas de pago; ya se probó contra SQLite en un entorno aparte, pero falta la confirmación contra Postgres
- [ ] Crear un usuario + `PerfilUsuario` desde el admin, probar login/logout, cambio de contraseña y recuperación (el correo sale por consola con el backend por defecto)
- [ ] Confirmar que un usuario con rol docente no puede entrar a la alta rápida/importación de una sección que no es la suya (403)
- [ ] Cargar una `TasaCambio` desde el admin y correr `python manage.py test cambio` (deben pasar todas las pruebas)
- [ ] Ver el dashboard nuevo en `/` (ya no es un placeholder, ahora exige login) y revisar el sidebar/topbar en escritorio y en móvil (el botón hamburguesa abre el menú)
- [ ] Correr `python manage.py collectstatic` en local para confirmar que `static/css/edumia.css` y `static/img/*` se recogen sin error (necesario para que Render los sirva en producción)
- [ ] Antes de que la recuperación de contraseña sirva de verdad en producción: configurar `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` y las variables `EMAIL_HOST*` en Render

## Fase 3 — Ingresos
- [x] Modelos `ingresos` (`docs/MODELOS_cambio_ingresos.md`, aprobado): `Banco` (catálogo), `FormaPago` (con las 5 banderas: banco destino/origen, referencia, teléfono, cédula), `ConceptoIngreso` (periodicidad única/mensual, monto y moneda sugeridos, fondo), `MontoConcepto` (monto esperado por concepto+grado+período, único, D-07) y `Aporte` (con `MontoBimonedaMixin` nuevo en `cambio/models.py`, compartido a futuro con `Gasto` de la Fase 5). `Aporte.inscripcion` es opcional (D-19: ingresos sin estudiante — rifas, donaciones). `SerieRecibo`/`Recibo` NO se construyen aquí: son de la Fase 4.
- [x] `Aporte.clean()` implementa las 9 validaciones del diseño: banderas de `forma_pago`, quién entrega obligatorio, fecha dentro del período (y período no cerrado), monto positivo, inscripción activa, mes cubierto obligatorio si el concepto es mensual, y desviación del monto esperado (±`UMBRAL_DESVIACION_MONTO`, ya en `settings`) comparando convertido a la moneda del esperado (I-2), no solo cuando coinciden literalmente.
- [x] `Aporte.transicionar(nuevo_estado, usuario, motivo)`: único método que cambia `estado` (borrador→registrado→verificado/observado→…→anulado), valida las transiciones permitidas, exige motivo en observado/anulado. La emisión del recibo al verificar queda pendiente de conectar cuando exista `Recibo` (Fase 4).
- [x] `TasaCambio` (en `cambio/models.py`) ahora bloquea su propia edición de `valor` si ya tiene aportes asociados (D-02, regla que estaba pendiente de que existiera una transacción que la referenciara).
- [x] Migración `ingresos/migrations/0001_initial.py` (incluye `HistoricalAporte`, `simple-history`). `seed_datos_iniciales` ahora también carga el catálogo de 24 bancos venezolanos y las 5 formas de pago sugeridas del diseño (Efectivo, Divisa efectivo, Pago móvil, Transferencia, Zelle) — idempotente.
- [x] Validado en este entorno (no en el tuyo, que no tiene Shell): se instaló Django en un sandbox aparte, se corrió `makemigrations --check` (sin cambios pendientes), `migrate` contra SQLite limpio, la suite `cambio` completa (15 pruebas, sigue en verde) y un script manual con 13 casos (montos, desviación, banderas de forma de pago, máquina de estados, inmutabilidad D-09, bloqueo de edición de tasa) — todos pasaron. Aun así, **falta correr `makemigrations`/`migrate` contra tu Postgres real** (ver pendientes de validación abajo): el comportamiento de `UniqueConstraint`/`CheckConstraint` puede diferir entre SQLite y Postgres.
- [x] Registro individual de aportes: `ingresos/forms.py` (`AporteForm`, con los `<select>` filtrados a inscripciones activas del período, conceptos/formas de pago/bancos activos y las últimas 30 tasas) y `ingresos/views.py` (`aporte_registrar`) — accesible para administrador y responsable de fondo (`ROLES_REGISTRO`), queda en estado «registrado». Enlazado desde el botón "Registrar ingreso" del dashboard y desde el menú "Ingresos".
- [x] Bandeja de verificación (`aporte_bandeja`): lista los aportes «registrado»/«observado»; administrador y responsable de fondo la ven, pero solo el administrador tiene los botones Verificar/Observar/Anular (`ROLES_VERIFICACION`) — el responsable ve "Esperando al administrador". Observar y anular piden motivo (`aporte_motivo.html`, plantilla compartida) y usan `Aporte.transicionar()`, nunca escriben `estado` a mano.
- [x] Validado con el mismo sandbox: 22 casos con el `Client` de pruebas de Django contra las vistas reales (no solo el modelo) — acceso anónimo redirige a login, rol sin permiso da 403, el POST válido autocompleta `periodo`/`fondo` (confirma que `AporteForm._post_clean()` sortea el bypass de `full_clean()` que hacen los `ModelForm`), responsable de fondo no puede verificar, la máquina de estados observado→registrado→verificado funciona desde las vistas, verificar dos veces no rompe nada, y la desviación de monto (convertida de moneda) bloquea el registro hasta marcar la casilla de confirmación. También un smoke test del dashboard y `/admin/` con los tres roles — nada se rompió.
- [ ] `FormaPago` con formulario propio en Configuración (por ahora solo se administra desde `/admin/`, como Sección antes de tener su CRUD)
- [ ] Registro en lote por sección (para el docente, pantalla aparte — siguiente paso natural)
- [ ] Búsqueda por referencia, cédula y teléfono
- [ ] `ConceptoIngreso`/`MontoConcepto` con CRUD en Configuración (por ahora solo admin)

## Fase 4 — Recibos
- [ ] `SerieRecibo` con `select_for_update()`
- [ ] Plantilla imprimible (media carta), con líneas de estudiante/sección omitidas cuando no aplica (D-19)
- [ ] Verificación pública por UUID + QR
- [ ] Reimpresión y marca de anulado
- [ ] Prueba de concurrencia de la numeración

## Fase 5 — Gastos
- [ ] Modelos `gastos` + migraciones
- [ ] Catálogos (fondos, categorías, productos, unidades, proveedores)
- [ ] Formset dinámico de renglones (HTMX)
- [ ] Subtotales, total, aprobación y anulación
- [ ] Saldo por fondo

## Fase 6 — Reportes y balance
- [ ] Motor de filtros compartido
- [ ] Los once reportes
- [ ] Exportación a Excel y PDF con encabezado
- [ ] Tablero de balance con gráfico mensual
- [ ] Índices y revisión de N+1

## Fase 7 — PWA offline
- [ ] Cola IndexedDB con `uuid` de cliente
- [ ] Endpoint de sincronización idempotente
- [ ] Background Sync con reintentos (iOS: sincronizar al abrir)
- [ ] Indicador visual de pendientes
- [ ] Pruebas sin red y de duplicados

## Fase 8 — Producción
- [ ] Bitácora de auditoría y `simple-history` activos
- [ ] Backup automatizado externo (Neon no lo da gratis)
- [ ] Ping externo a `/salud/` si no se configuró antes (ver Fase 0)
- [ ] Manual de usuario por rol
- [ ] Capacitación
- [ ] Carga de datos históricos
- [ ] Marcha blanca de un mes en paralelo

## Bloqueos abiertos
- P-03 tasa oficial (Fase 2) · P-04 fondo contable (Fase 5) · P-05 tamaño de la escuela (Fase 3) · P-06 teléfonos de docentes (Fase 7) · P-07 confirmar D-06/D-07/pago parcial con el administrador (no bloquea Fase 1, sí el flujo de captura de Fase 3) · P-08 saldo entre períodos (Fase 5) · P-09 traslados entre fondos (Fase 5) · D-10 flujo de gastos
