# Edumia — Estado del proyecto

Regla: no se empieza una fase sin cerrar la anterior aquí.
Última actualización: 2026-09-22

**Fase actual:** 0 — Infraestructura (en curso)
**MVP:** Fases 0–4 (92–126 h)

| Fase | Nombre | Horas | Estado |
| --- | --- | --- | --- |
| 0 | Infraestructura y hosting | 8–12 | Pendiente |
| 1 | Núcleo académico | 20–28 | Pendiente |
| 2 | Usuarios, roles, tasa y PWA nivel 1 | 18–24 | Pendiente |
| 3 | Ingresos | 30–40 | Pendiente |
| 4 | Recibos | 16–22 | Pendiente |
| 5 | Gastos | 28–36 | Pendiente |
| 6 | Reportes y balance | 30–40 | Pendiente |
| 7 | PWA offline | 24–32 | Pendiente |
| 8 | Puesta en producción | 20–30 | Pendiente |

## Diseño (previo a la Fase 0)
- [x] Plan de desarrollo
- [x] `docs/DECISIONES.md` (D-01 a D-15, pendientes P-03 a P-09)
- [x] `docs/ESTADO.md`
- [x] Diseño detallado de modelos: `core` y `academico` (aprobado)
- [x] Diseño detallado de modelos: `cambio` (aprobado)
- [x] Diseño detallado de modelos: `ingresos`, incluye `MontoConcepto` (aprobado)
- [x] Diseño detallado de modelos: `gastos` (aprobado; G-7 y G-8 abiertas)
- [ ] Confirmar D-06 y D-07 con el administrador (P-07)

## Fase 0 — Infraestructura
- [ ] Verificar versión de Python del venv (3.11 o 3.12)
- [ ] Repo, venv, `requirements.txt`, `.env.example`, `.gitignore`
- [ ] Esqueleto Django con settings base/local/production
- [ ] Cuenta Neon + `DATABASE_URL` (ramas `main` y `dev`)
- [ ] "Hola mundo" en Koyeb y medición de latencia desde Barquisimeto
- [ ] HTTPS confirmado en el dominio de Koyeb
- [ ] Vista `/salud/` sin consultas a la BD
- [ ] Decisión de hosting validada en `DECISIONES.md`

*Cierre: la app responde en una URL pública con Postgres conectado.*

## Fase 1 — Núcleo académico
- [ ] Modelos `core` y `academico` + migraciones
- [ ] Admin configurado
- [ ] Carga inicial: período, grados, secciones
- [ ] Importación de estudiantes desde Excel/CSV
- [ ] CRUD de estudiantes y representantes
- [ ] Promoción masiva al período siguiente

## Fase 2 — Usuarios, roles, tasa y PWA nivel 1
- [ ] `PerfilUsuario`, grupos y permisos
- [ ] Mixins y filtrado por sección en `get_queryset`
- [ ] Login, cambio y recuperación de contraseña
- [ ] `TasaCambio` + carga manual + servicio de conversión
- [ ] Pruebas unitarias del servicio de conversión
- [ ] `manifest.json`, íconos, service worker (shell + offline)
- [ ] Instalación verificada en Android y escritorio

## Fase 3 — Ingresos
- [ ] Modelos `ingresos` (incluye `MontoConcepto`) + migraciones
- [ ] `FormaPago` con banderas por campo + formulario HTMX
- [ ] Aporte individual y registro en lote por sección
- [ ] Bandeja de verificación
- [ ] Transiciones de estado y anulación con motivo
- [ ] Búsqueda por referencia, cédula y teléfono

## Fase 4 — Recibos
- [ ] `SerieRecibo` con `select_for_update()`
- [ ] Plantilla imprimible (media carta)
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
- [ ] Backup automatizado externo
- [ ] Manual de usuario por rol
- [ ] Capacitación
- [ ] Carga de datos históricos
- [ ] Marcha blanca de un mes en paralelo

## Bloqueos abiertos
- P-03 tasa oficial (Fase 2) · P-04 fondo contable (Fase 5) · P-05 tamaño de la escuela (Fase 3) · P-06 teléfonos de docentes (Fase 7) · P-07 confirmar D-06/D-07/pago parcial con el administrador (antes de Fase 1) · P-08 saldo entre períodos (Fase 5) · P-09 traslados entre fondos (Fase 5) · D-10 flujo de gastos
