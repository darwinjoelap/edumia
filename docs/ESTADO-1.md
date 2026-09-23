# Edumia — Estado del proyecto

Regla: no se empieza una fase sin cerrar la anterior aquí.
Última actualización: 2026-09-22

**Fase actual:** 1 — Núcleo académico (modelos creados, falta admin verificado, datos iniciales y vistas)
**MVP:** Fases 0–4 (92–126 h)

| Fase | Nombre | Horas | Estado |
| --- | --- | --- | --- |
| 0 | Infraestructura y hosting | 8–12 | **Cerrada** (hosting: Render, no Koyeb — D-17/D-18) |
| 1 | Núcleo académico | 20–28 | En curso |
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

## Fase 1 — Núcleo académico (en curso, 2026-09-22)
- [x] Modelos `core`: `Institucion`, `PeriodoEscolar`, `RegistroAuditoria` + migración aplicada en `dev` local
- [x] Admin de `core` configurado (Institución como singleton, bitácora de solo lectura)
- [x] Modelos `academico`: `Grado`, `Seccion`, `Estudiante`, `Representante`, `EstudianteRepresentante`, `Inscripcion` + migración aplicada en `dev` local (incluye historial de `Estudiante`, `Representante`, `Inscripcion`)
- [x] Admin de `academico` configurado (inlines de inscripción y representantes en el estudiante)
- [x] Verificar admin en el navegador
- [ ] `PerfilUsuario` queda para la Fase 2 (no en esta fase, ver nota abajo); la validación de rol del docente en `Seccion.clean()` ya está escrita a prueba de esa ausencia
- [x] Datos iniciales: `Institucion` (ejemplo, editar en admin), `PeriodoEscolar` 2026-2027 activo, 14 `Grado` (Inicial, Primaria, Media) — comando `seed_datos_iniciales`, idempotente
- [x] Alta rápida de estudiantes por sección (D-20): vista de tabla en `/academico/secciones/<id>/alta-rapida/`, varias filas de una vez, filas vacías se ignoran, cédulas repetidas se validan; sin restricción de rol todavía (llega en Fase 2) — probado en el navegador
- [ ] Importación de estudiantes desde Excel/CSV (formato genérico; sin archivo real de la escuela aún — se prueba con datos de ejemplo)
- [ ] CRUD de representantes (vínculo con estudiantes vía `EstudianteRepresentante`)
- [ ] Acción masiva de promoción al período siguiente
- [ ] Migrar y verificar también en Neon `production` cuando la fase esté completa (no antes, para no ensuciar producción con datos de prueba)

*Cierre: la nómina real de la escuela cargada y navegable.*

## Fase 2 — Usuarios, roles, tasa y PWA nivel 1
- [ ] `PerfilUsuario`, grupos y permisos por rol
- [ ] Mixins de permisos y filtrado por sección en `get_queryset` (incluye restringir la alta rápida de estudiantes de la Fase 1 a "solo mi sección" para el rol docente)
- [ ] Login, cambio y recuperación de contraseña
- [ ] `TasaCambio` + carga manual + servicio de conversión
- [ ] Pruebas unitarias del servicio de conversión
- [ ] `manifest.json`, íconos, service worker (shell + offline)
- [ ] Instalación verificada en Android y escritorio

## Fase 3 — Ingresos
- [ ] Modelos `ingresos` (incluye `MontoConcepto`, y `Aporte.inscripcion` opcional por D-19) + migraciones
- [ ] `FormaPago` con banderas por campo + formulario HTMX
- [ ] Aporte individual y registro en lote por sección
- [ ] Registro de ingresos sin estudiante (rifas, donaciones — D-19)
- [ ] Bandeja de verificación
- [ ] Transiciones de estado y anulación con motivo
- [ ] Búsqueda por referencia, cédula y teléfono

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
