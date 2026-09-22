# Edumia — Plan de desarrollo

Sistema de gestión de ingresos y gastos para una institución educativa pública

2026-09-21 · @Someone

## Resumen y decisiones fijadas

Edumia es un sistema Django para registrar, verificar y reportar los ingresos (aportes por estudiante) y los gastos (con desglose por renglón) de una institución educativa pública, con doble moneda real y tasa de cambio congelada por transacción.

Lo que hace distinto a Edumia frente a un control de gastos genérico son tres cosas: el aporte nace en el aula (el docente registra, el administrador verifica), el gasto se registra fragmentado (una compra de comedor = una cabecera + N renglones con su propio precio), y todo monto vive en Bs. y USD a la vez con la tasa del día.

| Decisión | Valor | Nota |
| --- | --- | --- |
| Alcance | Una sola institución | Sin multi-tenant; se deja un `Institucion` singleton para datos de encabezado de recibos |
| Moneda | Bimoneda real | Cada transacción guarda monto, moneda de origen, tasa y ambos equivalentes |
| Framework | Django + PostgreSQL | Plantillas server-side + HTMX; sin SPA |
| Interfaz | PWA instalable | Ícono en el móvil del docente y registro tolerante a caídas de señal |
| Hosting | Koyeb (web) + Neon (Postgres) | Ambos en capa gratuita, sin tarjeta |
| Archivos | Ninguno | Los datos del pago se transcriben como texto, no se suben imágenes |
| Idioma / zona | es-VE, America/Caracas | Formato de fecha dd/mm/aaaa, decimales con coma en la vista |

Un supuesto que conviene confirmar: el flujo docente registra → administrador verifica aplica solo a los aportes de estudiantes. Los gastos los registra directamente quien administra el fondo (comedor, tesorería) y el administrador los aprueba.

## Hosting gratuito: evaluación y recomendación

PythonAnywhere ya no es la mejor opción para Edumia: desde enero de 2026 las cuentas gratuitas nuevas no incluyen base de datos MySQL ni tareas programadas, y la web app expira a 1 mes de inactividad en vez de 3 ([anuncio oficial](https://blog.pythonanywhere.com/221/), [features de cuentas gratis](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/)). Sin base de datos gestionada, quedarías con SQLite sobre 512 MiB de disco, que para un sistema contable con múltiples usuarios escribiendo a la vez es un riesgo real de bloqueo y de pérdida de datos.

| Plataforma | Qué da gratis | Contra para Edumia |
| --- | --- | --- |
| PythonAnywhere (cuenta nueva) | 1 web app, 512 MiB disco, 100 s CPU/día, sin sleep | Sin MySQL ni Postgres, sin tareas programadas, expira al mes sin uso |
| PythonAnywhere (cuenta anterior a 15-ene-2026) | Lo anterior + MySQL + 1 tarea diaria | Solo si ya tenías la cuenta creada; verifícalo |
| Render | 750 h/mes de web service, Postgres 1 GB | La app duerme a los 15 min (arranque \~1 min) y el Postgres gratis **expira a los 30 días**, sin backups ([docs](https://render.com/docs/free)) |
| Koyeb | 1 servicio web siempre activo, Postgres gratis limitado | Cuota de horas de Postgres ajustada; menos documentación en español |
| Neon (solo BD) | 0.5 GB por proyecto, 100 CU-h/mes, Postgres real | Suspende el compute a los 5 min de inactividad (reconexión \~1 s) ([planes](https://neon.com/docs/introduction/plans)) |
| Supabase (solo BD) | 500 MB, 2 proyectos | Pausa el proyecto tras 1 semana sin uso, sin backups automáticos ([precios](https://supabase.com/pricing)) |

**Decidido: Koyeb (web) + Neon (Postgres).** Koyeb mantiene el servicio activo sin dormir, así que el docente que entra a las 7 de la mañana no espera un minuto de arranque en frío. Neon aporta un Postgres real que no expira a los 30 días como el gratuito de Render. Render queda como plan de respaldo si Koyeb cambia su capa gratuita.

En Fase 0 conviene igual medir el arranque en Koyeb con la app real: si el servicio resulta que sí se suspende por inactividad prolongada, se resuelve con el mismo ping externo gratuito (UptimeRobot o cron-job.org) cada 10 minutos.

Regla de diseño transversal: nada del código debe depender del proveedor. Todo por variables de entorno (`DATABASE_URL`, `SECRET_KEY`, `ALLOWED_HOSTS`), `dj-database-url` para la conexión, `whitenoise` para estáticos y almacenamiento de media desacoplado. Así migrar de Render a Koyeb, a PythonAnywhere pago o a un VPS es cambiar variables, no reescribir.

**Sin almacenamiento de archivos.** Edumia no guarda imágenes ni capturas de pantalla: los datos del pago se escriben como texto estructurado (referencia, banco, teléfono emisor, cédula del titular). Esto elimina la dependencia de S3/R2, deja la base de datos pequeña, evita el problema del disco efímero y — lo más importante — hace los datos **consultables**: puedes buscar por referencia o por cédula del titular, cosa imposible con una foto.

## Roles y permisos

Cinco roles, implementados con `Group` de Django más un modelo `PerfilUsuario` que ata al usuario con su sección o su fondo. Nadie borra: todo es anulación con motivo.

| Rol | Registra | Verifica / aprueba | Ve | No puede |
| --- | --- | --- | --- | --- |
| Administrador | Todo | Aportes y gastos | Todo | Borrar físicamente registros |
| Docente responsable | Aportes de **su** sección | — | Sus estudiantes y sus aportes | Ver otras secciones, editar un aporte verificado |
| Responsable de fondo (comedor, tesorería) | Gastos de su fondo con desglose | — | Sus gastos y saldo de su fondo | Registrar aportes, ver gastos de otro fondo |
| Director | — | — | Todos los reportes y el balance | Registrar o modificar nada |
| Auditor | — | — | Reportes + bitácora de auditoría | Cualquier escritura |

El flujo de un aporte:

```mermaid
flowchart LR
  A[Docente<br/>registra aporte] --> B{Administrador<br/>revisa}
  B -->|Conforme| C[Verificado<br/>+ recibo emitido]
  B -->|Observado| D[Devuelto<br/>al docente]
  D --> A
  C --> E{¿Error detectado?}
  E -->|Sí| F[Anulado<br/>con motivo]
```

Un aporte verificado queda inmutable. Si hay error, se anula con motivo y se registra uno nuevo; el recibo anulado conserva su número y queda marcado. Esto es lo que hace auditable el sistema ante una contraloría.

Detalle de implementación: el docente nunca elige la sección en el formulario. El queryset de estudiantes se filtra por la sección asignada a su perfil en el período activo, y cada vista valida la pertenencia en `get_queryset`, no solo en el template.

## Arquitectura y stack

Django 5.x con plantillas server-side y HTMX. Sin SPA: el volumen de datos de una escuela no lo justifica y una API + frontend separado duplica el trabajo de mantenimiento.

Apps Django, una por dominio de negocio:

| App | Responsabilidad |
| --- | --- |
| `core` | `Institucion`, `PeriodoEscolar`, `PerfilUsuario`, bitácora de auditoría, mixins de permisos |
| `academico` | `Grado`, `Seccion`, `Estudiante`, `Representante`, `Inscripcion` |
| `ingresos` | `ConceptoIngreso`, `Aporte`, `Recibo`, flujo de verificación |
| `gastos` | `CategoriaGasto`, `Proveedor`, `Fondo`, `Gasto`, `DetalleGasto`, `Producto`, `UnidadMedida` |
| `cambio` | `TasaCambio`, servicio de conversión, importación de tasa |
| `reportes` | Vistas de consulta, filtros, exportación a Excel y PDF |

Dependencias base, todas con licencia libre y sin costo:

| Paquete | Para qué |
| --- | --- |
| `django` | Framework |
| `psycopg[binary]` | Driver Postgres |
| `dj-database-url` | Conexión por `DATABASE_URL` |
| `python-decouple` o `django-environ` | Variables de entorno |
| `whitenoise` | Archivos estáticos en producción |
| `gunicorn` | Servidor WSGI |
| `django-htmx` | Interacciones parciales sin recargar |
| `weasyprint` | Recibos y reportes en PDF |
| `openpyxl` | Exportación a Excel |
| `django-crispy-forms` + `crispy-bootstrap5` | Formularios |
| `django-simple-history` | Historial de cambios por registro |

Sobre WeasyPrint: en Render funciona porque puedes instalar las dependencias del sistema; en PythonAnywhere gratis puede dar problemas. Alternativa liviana si falla: generar el recibo en HTML con CSS `@media print` y que el usuario imprima o guarde como PDF desde el navegador. Empieza por ahí — es más simple y cubre el 90% del caso.

Settings divididos: `config/settings/base.py`, `local.py`, `production.py`. `DEBUG=False` por defecto en producción, `ALLOWED_HOSTS` desde variable, `SECURE_SSL_REDIRECT` activo.

Decimales: `DecimalField(max_digits=18, decimal_places=4)` para montos y tasas. Nunca `FloatField` — con una tasa de cambio de cinco cifras los errores de coma flotante aparecen en el primer balance.

## PWA — instalable y tolerante a la conectividad

Edumia se instala en el teléfono del docente como una aplicación: ícono en la pantalla de inicio, sin barra del navegador, y funcionando aunque la señal en la escuela se caiga a mitad de un registro.

Tres piezas, todas sin dependencias de pago:

| Pieza | Qué hace |
| --- | --- |
| `manifest.json` | Nombre, íconos (192 y 512 px), `display: standalone`, color de tema, `start_url` |
| `service-worker.js` | Cachea el shell de la app (CSS, JS, íconos, página offline) y sirve desde caché cuando no hay red |
| IndexedDB | Cola local de aportes registrados sin conexión, que se sincroniza al volver la señal |

Estrategias de caché, por tipo de recurso:

- **Estáticos** (CSS, JS, íconos, fuentes): cache-first. Cambian poco y deben cargar instantáneo.
- **Páginas de consulta** (listados, reportes): network-first con respaldo en caché. Si hay red, datos frescos; si no, la última versión vista con un aviso de "datos del ‹fecha›".
- **Escrituras** (registrar aporte, registrar gasto): nunca desde caché. Si no hay red, entran a la cola de IndexedDB.

El flujo offline del docente:

```mermaid
flowchart LR
  A[Docente registra<br/>aporte en el móvil] --> B{¿Hay conexión?}
  B -->|Sí| C[POST al servidor<br/>estado: registrado]
  B -->|No| D[Cola en IndexedDB<br/>marca: pendiente]
  D --> E[Vuelve la señal]
  E --> F[Background Sync<br/>envía la cola]
  F --> C
```

Dos reglas que evitan duplicados al sincronizar: cada aporte encolado lleva un `uuid` generado en el cliente, y el endpoint de sincronización es idempotente — si ese `uuid` ya existe, responde OK sin crear nada. Sin esto, una sincronización reintentada duplica los aportes, que en un sistema contable es el peor error posible.

La interfaz debe dejar clarísimo el estado: un aporte pendiente de sincronizar se ve distinto de uno ya en el servidor. El docente tiene que saber que todavía no está guardado de verdad.

Requisito técnico: el service worker exige HTTPS. Koyeb lo da por defecto en su dominio, así que no hay trabajo extra.

Alcance por fases: el manifest y el caché del shell (la parte "instalable") son baratos y entran en la Fase 2. La cola offline con IndexedDB es bastante más trabajo y va en una fase propia, después de que el registro en línea funcione bien. Conviene no mezclarlas.

## Modelo de datos — núcleo académico

La decisión clave: **el estudiante no guarda su grado ni su sección**. Esa relación vive en `Inscripcion`, una fila por estudiante y período escolar. Así el alumno pasa de grado sin que se rompa el histórico y los reportes de años anteriores siguen siendo correctos.

| Modelo | Campos principales |
| --- | --- |
| `PeriodoEscolar` | `nombre` (2025-2026), `fecha_inicio`, `fecha_fin`, `activo` (único True) |
| `Grado` | `nombre`, `nivel` (inicial/primaria/media), `orden` |
| `Seccion` | `grado` FK, `nombre` (A, B, U), `periodo` FK, `docente_responsable` FK a User |
| `Estudiante` | `cedula_escolar` única, `nombres`, `apellidos`, `fecha_nacimiento`, `sexo`, `activo` |
| `Representante` | `cedula` única, `nombres`, `apellidos`, `telefono`, `email`, `direccion`, `parentesco` |
| `EstudianteRepresentante` | `estudiante` FK, `representante` FK, `es_principal` |
| `Inscripcion` | `estudiante` FK, `seccion` FK, `periodo` FK, `fecha`, `estado` (activo/retirado/egresado) |

Un estudiante puede tener más de un representante (madre y padre, o un tercero autorizado), por eso la tabla intermedia y no una FK simple. El recibo se emite a nombre de quien entregó el aporte, que puede no ser el principal.

```mermaid
flowchart LR
  P[PeriodoEscolar] --> S[Seccion]
  G[Grado] --> S
  S --> I[Inscripcion]
  E[Estudiante] --> I
  E --> ER[EstudianteRepresentante]
  R[Representante] --> ER
  S --> D[Docente<br/>responsable]
```

Operaciones que debes poder hacer desde el panel, sin tocar la base de datos:

- Corregir datos de un estudiante o representante (nombre mal escrito, teléfono, cédula)
- Cambiar a un estudiante de sección dentro del mismo período (se edita su `Inscripcion`)
- Promover en lote a toda una sección al período siguiente (acción masiva que crea las nuevas `Inscripcion`)
- Marcar un estudiante como retirado sin perder sus aportes históricos
- Reasignar el docente responsable de una sección a mitad de año

El cierre de período no borra nada: crea un `PeriodoEscolar` nuevo, se marca activo, y las inscripciones anteriores quedan como historia consultable.

## Modelo de datos — ingresos (aportes)

El aporte es el corazón del sistema. Cada fila responde: quién aportó, por cuál estudiante, cuánto, en qué moneda, cómo pagó, quién lo registró y quién lo verificó.

| Modelo | Campos principales |
| --- | --- |
| `ConceptoIngreso` | `nombre` (Aporte mensual, Rifa, Donación), `es_recurrente`, `monto_sugerido`, `moneda_sugerida`, `activo` |
| `FormaPago` | `nombre` (Efectivo, Pago móvil, Transferencia, Zelle, Divisa efectivo), `requiere_referencia` |
| `Banco` | `nombre`, `codigo` (0102, 0105…), `activo` |
| `Aporte` | ver desglose abajo |
| `Recibo` | `aporte` OneToOne, `numero` correlativo, `fecha_emision`, `anulado`, `motivo_anulacion` |

Campos de `Aporte`:

- Identidad: `inscripcion` FK (de ahí salen estudiante, sección, grado y período), `concepto` FK, `periodo` FK denormalizado para consultas rápidas
- Dinero: `monto`, `moneda` (VES/USD), `tasa_aplicada`, `monto_ves`, `monto_usd`, `tasa` FK a `TasaCambio`
- Pago: `forma_pago` FK, `fecha_pago` — ver el bloque de datos bancarios abajo
- Entrega: `entregado_por` FK a `Representante` nullable, `entregado_por_nombre` texto libre para cuando no es un representante registrado
- Flujo: `estado` (borrador / registrado / verificado / observado / anulado), `registrado_por` FK User, `fecha_registro`, `verificado_por` FK User, `fecha_verificacion`, `observacion`
- Auditoría: `creado_en`, `actualizado_en`, historial vía `django-simple-history`

**Datos bancarios como texto, no como imagen.** No se sube el comprobante: se transcriben los datos que permiten conciliar con el estado de cuenta del banco.

| Campo | Contenido | Obligatorio cuando |
| --- | --- | --- |
| `banco_destino` | FK a `Banco`: a dónde entró el dinero | Transferencia, pago móvil |
| `banco_origen` | FK a `Banco`: de dónde salió | Pago móvil |
| `referencia` | Número de referencia de la operación | `forma_pago.requiere_referencia` |
| `telefono_emisor` | Teléfono desde el que se hizo el pago móvil | Pago móvil |
| `cedula_titular` | Cédula del titular de la cuenta emisora | Transferencia, pago móvil |
| `nombre_titular` | Nombre del titular, si difiere de quien entrega | Opcional |
| `nota_pago` | Texto libre para casos atípicos | Opcional |

`forma_pago` deja de tener un solo `requiere_referencia` y pasa a tener banderas por campo: `requiere_referencia`, `requiere_banco_origen`, `requiere_telefono`, `requiere_cedula`. Así el efectivo no pide nada, el pago móvil pide los cuatro y una transferencia pide tres, sin escribir condicionales a mano por cada forma de pago.

El formulario muestra u oculta esos campos con HTMX según la forma de pago elegida, y la validación real vive en `clean()` leyendo las banderas.

Reglas que se codifican, no se confían al usuario:

1. Cada campo bancario es obligatorio según las banderas de su `FormaPago`, validado en el modelo.
2. La combinación `banco_destino + referencia + fecha_pago` debe ser única — evita registrar dos veces la misma transferencia. Se implementa con `UniqueConstraint` condicional (solo cuando hay referencia).
3. `cedula_titular` y `telefono_emisor` se normalizan al guardar (sin puntos, sin guiones, teléfono a 11 dígitos) para que la búsqueda funcione.
4. Un `Aporte` en estado `verificado` no admite edición de montos ni de estudiante; solo anulación.
5. El recibo se emite en la transición a `verificado`, no antes.
6. Un aporte no puede quedar fuera del rango de fechas de su período escolar.

Un detalle que ahorra dolores: el docente registra en lote. La pantalla natural para él es la lista de su sección con una columna de monto y una de referencia, y un solo botón de guardar — no un formulario por estudiante.

## Modelo de datos — gastos fragmentados

El requisito del comedor — tomate, cebolla y harina comprados en momentos distintos y a precios distintos — se resuelve con el patrón cabecera + detalle, el mismo de una factura.

| Modelo | Campos principales |
| --- | --- |
| `Fondo` | `nombre` (Comedor, Mantenimiento, General), `responsable` FK User, `activo` |
| `CategoriaGasto` | `nombre` (Víveres, Limpieza, Papelería, Servicios), `fondo` FK nullable |
| `UnidadMedida` | `nombre` (Kg, Litro, Unidad, Bulto), `abreviatura` |
| `Producto` | `nombre` (Tomate), `categoria` FK, `unidad_default` FK |
| `Proveedor` | `nombre`, `rif`, `telefono`, `direccion` |
| `Gasto` (cabecera) | `fecha`, `fondo` FK, `proveedor` FK nullable, `tipo_documento` (factura/nota/recibo/sin soporte), `numero_documento`, `moneda`, `tasa` FK, `estado`, `registrado_por`, `aprobado_por`, `observacion` |
| `DetalleGasto` (renglón) | `gasto` FK, `producto` FK, `descripcion` libre, `cantidad`, `unidad` FK, `precio_unitario`, `moneda_linea`, `subtotal` calculado |

El punto fino: **el precio unitario vive en el renglón, no en el producto**. `Producto` es solo un catálogo para normalizar nombres y poder preguntar "cuánto gastamos en tomate este trimestre". El precio de cada compra queda congelado en su `DetalleGasto`, así que el historial de precios sale gratis de una consulta.

Dos casos de uso que el modelo debe cubrir:

- **Una compra, varios rubros**: la señora del comedor va al mercado y trae tomate, cebolla y ajo. Un `Gasto` con tres `DetalleGasto`. Un solo documento, un solo total.
- **Un rubro comprado en días distintos**: el tomate del lunes a un precio y el del jueves a otro. Dos `Gasto` distintos, cada uno con su renglón de tomate y su propio precio. La consulta por producto los suma correctamente.

`subtotal` se calcula y se guarda (no se deriva en cada lectura) para que los reportes no dependan de recalcular miles de filas. El total del `Gasto` se recalcula por señal o por método explícito cada vez que cambia un renglón.

Sobre el saldo del fondo: `saldo = suma de aportes asignados al fondo − suma de gastos aprobados del fondo`. Si un aporte no se asigna a un fondo específico entra al fondo General. Conviene un campo `fondo` nullable en `ConceptoIngreso` para automatizar esa asignación.

Menos obvio pero importante: el gasto también necesita estado y aprobación. `registrado → aprobado → anulado`, con las mismas reglas de inmutabilidad que el aporte. Sin eso, el balance cambia cada vez que alguien edita una compra vieja.

## Bimoneda y tasa de cambio

La regla de oro: **la tasa se congela en la transacción**. Un aporte registrado el 3 de marzo se reporta siempre con la tasa del 3 de marzo, sin importar que hoy la tasa sea otra. Sin esto, el balance de enero cambia solo cada mañana.

`TasaCambio`: `fecha` (única), `valor` (Bs. por USD, `max_digits=18, decimal_places=4`), `fuente` (BCV / paralelo / manual), `cargada_por`, `creada_en`.

Toda transacción — aporte y gasto — lleva el mismo bloque de campos:

| Campo | Contenido |
| --- | --- |
| `monto` | Lo que la persona escribió |
| `moneda` | VES o USD, la moneda en que ocurrió realmente |
| `tasa` | FK a `TasaCambio` |
| `tasa_aplicada` | Copia del valor numérico, por si la tasa se corrige después |
| `monto_ves` | Calculado y guardado |
| `monto_usd` | Calculado y guardado |

Se guardan los dos equivalentes, no se calculan al vuelo. Así cualquier reporte suma con un `Sum()` simple y los totales cuadran siempre.

Cómo entra la tasa del día, en orden de preferencia:

1. **Carga manual por el administrador** — un formulario, una fila por día. Simple, sin dependencias, funciona siempre. Empieza aquí.
2. **Importación desde una API pública del BCV** con un botón "actualizar tasa de hoy". Riesgo: esas APIs no oficiales se caen.
3. **Tarea programada diaria** — no disponible en los planes gratuitos que evaluamos, se sustituye con un ping externo a una vista protegida por token.

Comportamiento si no hay tasa cargada para la fecha: el sistema toma la última tasa anterior disponible y **avisa visiblemente** en el formulario ("usando la tasa del 18/09, cargue la de hoy"). No bloquea el registro — en una escuela nadie puede quedarse sin registrar un pago porque faltó cargar un número.

Redondeo: se guarda con 4 decimales y se muestra con 2. Todas las conversiones usan `Decimal` con `ROUND_HALF_UP` en un solo servicio (`cambio/services.py`), nunca dispersas por las vistas.

Si luego aparece una tasa BCV y una paralela conviviendo, el campo `fuente` ya está y solo se agrega el criterio de cuál usar por concepto. Vale la pena dejarlo previsto desde el modelo aunque no se use al inicio.

## Recibos

Quien entrega el aporte se lleva un comprobante. Ese papel es lo que le da credibilidad al sistema frente a los representantes, así que conviene hacerlo bien desde la primera versión.

Qué lleva el recibo: logo y datos de la institución, número correlativo, fecha de emisión, nombre de quien entregó, estudiante y su sección, concepto, monto en Bs. y en USD con la tasa aplicada, forma de pago con banco y referencia, nombre del docente que registró, y un código o QR de verificación.

La numeración correlativa es el punto delicado. Dos docentes verificando a la vez pueden generar el mismo número. Se resuelve con un modelo `SerieRecibo` (`prefijo`, `ultimo_numero`) y la asignación dentro de una transacción con `select_for_update()`. Nunca con `max(numero) + 1` en Python — eso falla bajo concurrencia.

Formato del número: `2025-2026-000147` — período escolar más correlativo de seis dígitos. El correlativo reinicia por período, que es lo que espera una contraloría.

Anulación: el número **no se reutiliza**. El recibo queda con `anulado=True` y `motivo_anulacion`, sigue apareciendo en los listados marcado en rojo, y el aporte corregido genera un recibo nuevo con número nuevo.

Entrega: vista HTML imprimible como primera versión (CSS `@media print`, tamaño media carta, dos copias por hoja — una para el representante, otra para archivo). PDF con WeasyPrint después, cuando confirmes que el hosting lo soporta. Envío por WhatsApp o correo queda para una fase posterior.

Verificación pública: una URL como `/recibo/<uuid>/` que muestra los datos del recibo sin requerir login. El representante escanea el QR y confirma que su aporte está registrado. Usa UUID, no el número correlativo, para que nadie enumere recibos ajenos.

## Reportes y balance

Un solo motor de consulta con filtros combinables, no veinte vistas distintas. Los filtros base: rango de fechas, período escolar, grado, sección, estudiante, representante, concepto, forma de pago, banco, estado, moneda, usuario que registró, usuario que verificó.

| Reporte | Responde a |
| --- | --- |
| Estado de cuenta por estudiante | ¿Qué ha aportado este alumno y qué debe? |
| Consolidado por sección | ¿Cuánto recaudó 5to “A” y quiénes faltan? |
| Consolidado por grado | Comparativo entre secciones del mismo grado |
| Recaudación por concepto | ¿Cuánto entró por rifa vs. aporte mensual? |
| Recaudación por forma de pago y banco | Para conciliar con el estado de cuenta bancario |
| Morosidad / pendientes | Inscritos sin aporte registrado en el período |
| Gastos por categoría y por fondo | ¿En qué se fue el dinero del comedor? |
| Historial de precios por producto | ¿A cómo compramos el tomate los últimos tres meses? |
| Gastos por proveedor | Concentración de compras |
| Balance general | Ingresos − gastos por período, con saldo por fondo |
| Bitácora de aportes por docente | Control de quién registra y cuánto falta verificar |

Cada reporte se ve en pantalla, se exporta a Excel (`openpyxl`) y se imprime en PDF con el encabezado institucional. Todos muestran las dos monedas.

El balance general es el que verá el director. Debe caber en una pantalla: ingresos del período, gastos del período, saldo, y el desglose por fondo. Debajo, un gráfico de barras de ingresos vs. gastos por mes. Nada más en esa vista.

Rendimiento: agregar `select_related` e índices sobre `(periodo, estado)`, `(inscripcion, fecha_pago)` y `(fondo, fecha)` desde el inicio. Con 600 alumnos y un año de aportes hablas de unas 6.000 filas — nada, pero el plan gratuito de base de datos tiene poca CPU y las consultas mal armadas se notan.

## Reglas de negocio y auditoría

En un sistema que maneja dinero público, la trazabilidad importa tanto como la funcionalidad. Estas reglas son lo que diferencia a Edumia de una hoja de cálculo compartida.

**Nada se borra.** Ningún modelo transaccional expone `delete`. Aportes, gastos y recibos se anulan con motivo y quedan visibles. Estudiantes, representantes y proveedores se desactivan con `activo=False`.

**Inmutabilidad tras la verificación.** Un aporte verificado o un gasto aprobado no admite cambios de monto, fecha, moneda ni estudiante. Se implementa en `save()` y en `clean()`, no solo escondiendo el botón en el template.

**Historial completo.** `django-simple-history` sobre `Aporte`, `Gasto`, `DetalleGasto`, `Estudiante`, `Representante`, `Inscripcion` y `TasaCambio`. Con eso respondes "quién cambió este monto y cuándo" sin construir nada a mano.

**Bitácora de eventos.** Además del historial por registro, un modelo `RegistroAuditoria` (`usuario`, `accion`, `modelo`, `objeto_id`, `descripcion`, `ip`, `fecha`) para los eventos que importan: inicio de sesión, verificación, anulación, emisión de recibo, carga de tasa, cierre de período.

**Edición de datos de personas.** Corregir el nombre de un estudiante o el teléfono de un representante es una operación normal del administrador y queda registrada en el historial. Lo que nunca cambia retroactivamente es un recibo ya emitido: ese conserva el nombre tal como se imprimió.

**Cierre de período.** Al cerrar un período escolar se bloquea el registro de aportes y gastos con fecha dentro de él. Solo el administrador puede reabrirlo, y esa acción queda en la bitácora.

Dos validaciones que atrapan la mayoría de los errores humanos: referencia bancaria duplicada, y monto que se desvía mucho del `monto_sugerido` del concepto (no bloquea, pide confirmación — típicamente es un cero de más o de menos).

## Plan de fases

Nueve fases. Cada una cierra con algo desplegado y usable, no con código a medias. La regla: no se empieza una fase sin cerrar la anterior en `docs/ESTADO.md`.

**Fase 0 — Infraestructura y decisión de hosting**

- [ ] Verificar la versión de Python del venv antes de nada
- [ ] Crear repo, venv, `requirements.txt`, `.env.example`, `.gitignore`
- [ ] Esqueleto Django con settings divididos (base/local/production)
- [ ] Crear cuenta en Neon y obtener `DATABASE_URL`
- [ ] Desplegar un "hola mundo" en Koyeb y medir latencia desde Barquisimeto
- [ ] Confirmar HTTPS en el dominio de Koyeb (requisito del service worker)
- [ ] Documentar la decisión de hosting en `docs/DECISIONES.md`

*Cierre: la app responde en una URL pública con Postgres conectado.*

**Fase 1 — Núcleo académico**

- [ ] Modelos de `core` y `academico` + migraciones
- [ ] Admin de Django configurado para los seis modelos
- [ ] Carga inicial: período activo, grados, secciones
- [ ] Importación de estudiantes desde Excel/CSV
- [ ] CRUD de estudiantes y representantes en la interfaz pública
- [ ] Acción masiva de promoción al período siguiente

*Cierre: la nómina real de la escuela cargada y navegable.*

**Fase 2 — Usuarios, roles y tasa de cambio**

- [ ] `PerfilUsuario`, grupos y permisos por rol
- [ ] Mixins de permisos y filtrado por sección en `get_queryset`
- [ ] Login, cambio de contraseña, recuperación
- [ ] Modelo `TasaCambio` + carga manual + servicio de conversión
- [ ] Pruebas unitarias del servicio de conversión (el punto más propenso a errores)
- [ ] PWA nivel 1: `manifest.json`, íconos, service worker con caché del shell y página offline
- [ ] Verificar que la app se instala en Android y en escritorio

*Cierre: cada rol entra y ve solo lo suyo; la tasa del día se carga y se aplica.*

**Fase 3 — Ingresos**

- [ ] Modelos de `ingresos` + migraciones, con los campos bancarios de texto
- [ ] `FormaPago` con banderas por campo y formulario dinámico con HTMX
- [ ] Registro de aporte individual
- [ ] Registro en lote por sección (la pantalla del docente)
- [ ] Bandeja de verificación del administrador
- [ ] Transiciones de estado con sus validaciones
- [ ] Anulación con motivo
- [ ] Búsqueda de aportes por referencia, cédula del titular y teléfono emisor

*Cierre: un docente registra, el administrador verifica, queda en el balance.*

**Fase 4 — Recibos**

- [ ] `SerieRecibo` con numeración concurrente segura
- [ ] Plantilla imprimible con datos institucionales
- [ ] Vista pública de verificación por UUID + QR
- [ ] Reimpresión y marca de anulado
- [ ] Prueba de concurrencia de la numeración

*Cierre: el representante se lleva su recibo en papel.*

**Fase 5 — Gastos**

- [ ] Modelos de `gastos` + migraciones
- [ ] Catálogos: fondos, categorías, productos, unidades, proveedores
- [ ] Formulario de gasto con formset de renglones dinámico (HTMX)
- [ ] Cálculo de subtotales y total
- [ ] Aprobación y anulación de gastos
- [ ] Saldo por fondo

*Cierre: la compra del comedor se registra renglón por renglón.*

**Fase 6 — Reportes y balance**

- [ ] Motor de filtros compartido
- [ ] Los once reportes de la sección anterior
- [ ] Exportación a Excel
- [ ] Impresión en PDF con encabezado
- [ ] Tablero de balance con gráfico mensual
- [ ] Índices de base de datos y revisión de consultas N+1

*Cierre: el director abre el balance y entiende el estado financiero sin preguntarle a nadie.*

**Fase 7 — PWA offline**

- [ ] Cola de escrituras en IndexedDB con `uuid` generado en el cliente
- [ ] Endpoint de sincronización idempotente
- [ ] Background Sync con reintentos
- [ ] Indicador visual de registros pendientes de sincronizar
- [ ] Pruebas con la red apagada y reconexión a mitad de envío
- [ ] Prueba de duplicados: sincronizar dos veces la misma cola

*Cierre: el docente registra sin señal y todo llega completo al reconectar.*

**Fase 8 — Puesta en producción**

- [ ] Bitácora de auditoría y `simple-history` activos
- [ ] Backup automatizado a un destino externo
- [ ] Manual de usuario en español, por rol, con capturas
- [ ] Capacitación a docentes y administrador
- [ ] Carga de datos históricos del período en curso
- [ ] Marcha blanca de un mes en paralelo con el método actual

*Cierre: la escuela deja de usar el cuaderno.*

Una sugerencia sobre el orden: si necesitas mostrar avances pronto, las fases 1 a 4 ya constituyen un sistema útil por sí solas. Los gastos pueden esperar unas semanas; los aportes con recibo, no.

## Despliegue y operación

Pasos en Koyeb + Neon:

1. Crear el proyecto en Neon, copiar el `DATABASE_URL` con `?sslmode=require`.
2. En Koyeb, crear un servicio desde el repo de GitHub (buildpack de Python, sin Docker).
3. Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput`.
4. Run: `python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`.
5. Variables de entorno: `DATABASE_URL`, `SECRET_KEY`, `DEBUG=False`, `ALLOWED_HOSTS`, `DJANGO_SETTINGS_MODULE=config.settings.production`, `CSRF_TRUSTED_ORIGINS`.
6. Health check de Koyeb apuntando a `/salud/`, una vista liviana sin consultas a la base de datos.
7. Crear el superusuario desde la consola del servicio.
8. Verificar que el `manifest.json` y el service worker se sirven correctamente sobre HTTPS.

Backups — lo más importante y lo que más se descuida. Neon gratis no da backups programados, así que necesitas los tuyos:

- Un comando de gestión `python manage.py respaldo` que genere un dump y lo suba a Google Drive o R2
- Disparado por el mismo servicio de ping externo, una vez al día, en una vista protegida por token
- Alternativa manual pero honesta: `pg_dump` semanal desde tu máquina, guardado en Drive. Para una escuela es suficiente al inicio, siempre que lo hagas de verdad
- Exportación mensual a Excel de aportes y gastos: no es un backup técnico, pero salva el año si todo falla

Estáticos con `whitenoise` y compresión; no necesitas CDN. El service worker debe servirse desde la raíz del dominio (`/service-worker.js`) para poder controlar todas las rutas — con WhiteNoise se resuelve con una ruta explícita en `urls.py`, no colocándolo dentro de `/static/`.

No hay carpeta de media que respaldar ni que configurar: al no guardar archivos, el disco efímero del contenedor deja de ser un problema.

Seguridad mínima antes de producción: `DEBUG=False`, `SECRET_KEY` fuera del repo, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `X_FRAME_OPTIONS=DENY`, contraseñas con validadores activos, y `django-axes` o un limitador simple de intentos de login.

Un detalle sobre datos de menores: la base guarda nombres, cédulas escolares y datos de representantes. Aunque Venezuela no tenga un régimen tipo GDPR, vale la pena limitar quién ve qué y no exponer listados completos en URLs públicas.

## Riesgos y decisiones abiertas

| Riesgo | Impacto | Mitigación |
| --- | --- | --- |
| Koyeb cambia o recorta su capa gratuita | Hay que migrar | Código agnóstico por variables de entorno; Render como respaldo |
| Neon suspende el compute a los 5 min | Latencia extra en la primera consulta | Aceptable (\~1 s); un ping cada 10 min lo evita |
| 0.5 GB de base de datos | Suficiente para años de una escuela | Sin imágenes el crecimiento es mínimo |
| Sin backups del proveedor | Pérdida total de datos | Respaldo propio automatizado desde la Fase 0 |
| WeasyPrint puede fallar en el hosting | Sin PDF | Empezar con HTML imprimible |
| Duplicados al sincronizar la cola offline | Aportes contados dos veces | `uuid` de cliente + endpoint idempotente, probado explícitamente |
| El docente cree que guardó y estaba offline | Aporte no registrado | Indicador visual de pendientes, bien visible |
| Datos bancarios mal transcritos | No se puede conciliar con el banco | Normalización al guardar + validación de referencia duplicada |
| Docentes con poca destreza digital | El sistema no se usa | Registro en lote, PWA instalada como app, capacitación, marcha blanca |
| Tasa de cambio no cargada a diario | Conversiones con tasa vieja | Aviso visible + recordatorio al administrador al entrar |

Decisiones que debes tomar antes de escribir la primera migración:

1. **¿Los aportes son por estudiante o por representante?** Si una madre tiene tres hijos en la escuela y paga un solo monto, ¿se registran tres aportes o uno repartido? Esto cambia el modelo.
2. **¿Hay montos esperados por grado?** Si el aporte mensual varía por nivel, `ConceptoIngreso` necesita una tabla de montos por grado para que el reporte de morosidad funcione.
3. **¿Qué tasa es la oficial para la institución?** BCV, paralela, o la que fije el consejo directivo.
4. **¿Los gastos se pagan de un fondo común o cada aporte está amarrado a un destino?** Define si el saldo por fondo es contable o solo informativo.
5. **¿Cuántos alumnos y cuántas secciones?** Determina si conviene la pantalla de registro en lote o una búsqueda por cédula.
6. **¿Qué teléfonos usan los docentes?** Android mayoritario o mezcla con iPhone. Importa porque en iOS la PWA se instala a mano desde Safari y Background Sync no existe: ahí la cola offline tendría que sincronizar al abrir la app, no en segundo plano.

La número 1 es la que más cuesta cambiar después. Vale la pena preguntarle al administrador de la escuela antes de la Fase 1.

## Estimación de tiempo

Entre 200 y 265 horas de trabajo efectivo para el sistema completo. El rango no es incertidumbre pura: el extremo bajo asume que reutilizas patrones de BioLifeLab (estructura de settings, mixins de permisos, exportación a Excel), el alto asume construir todo desde cero.

| Fase | Horas | Comentario |
| --- | --- | --- |
| 0 — Infraestructura | 8–12 | Casi todo es configuración; una vez hecho no se repite |
| 1 — Núcleo académico | 20–28 | La importación desde Excel y la promoción masiva se llevan la mitad |
| 2 — Roles, tasa y PWA básica | 18–24 | El manifest y el caché del shell son \~4 h de esas |
| 3 — Ingresos | 30–40 | La fase más densa: formulario dinámico, registro en lote, flujo de estados |
| 4 — Recibos | 16–22 | La numeración concurrente y su prueba son lo fino |
| 5 — Gastos | 28–36 | El formset dinámico de renglones es lo que cuesta |
| 6 — Reportes y balance | 30–40 | Once reportes, pero comparten motor de filtros |
| 7 — PWA offline | 24–32 | Fácil de subestimar; la sincronización idempotente exige pruebas reales |
| 8 — Producción | 20–30 | Manual, capacitación y carga histórica, no código |
| **Total** | **194–264** |  |

En tiempo de calendario, según cuánto le dediques por semana:

| Dedicación | Sistema completo | Solo el MVP (Fases 0–4) |
| --- | --- | --- |
| 8 h/semana | 6 a 8 meses | 3 meses |
| 15 h/semana | 3,5 a 4,5 meses | 6 a 8 semanas |
| 25 h/semana | 2 a 2,5 meses | 4 a 5 semanas |

El MVP — fases 0 a 4 — suma 92 a 126 horas y ya es un sistema que la escuela puede usar: registra aportes, verifica y entrega recibos. Si tu tiempo está repartido con la maestría y BioLife, apunta a eso primero y deja gastos y reportes para un segundo tramo.

Dos cosas que la gente siempre subestima, y que ya están dentro del rango: los ajustes después de la primera demo al administrador de la escuela (siempre hay cambios de criterio al ver el sistema real), y la carga de datos históricos del período en curso. Cuenta esas dos como una fase más, no como un detalle.

## Guía de instalación — Fase 0 paso a paso

Pensada para VS Code + PowerShell en Windows. Cada bloque es copiable tal cual.

**1. Verificar Python.** Con varias versiones instaladas, esto es lo primero:

```
py --list
py -3.12 --version
```

Usa 3.11 o 3.12. Evita 3.13 por ahora: algunas ruedas binarias todavía se compilan y en Windows eso duele.

**2. Crear el proyecto y el entorno virtual:**

```
mkdir C:\proyectos\edumia
cd C:\proyectos\edumia
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Si PowerShell bloquea el script de activación:

```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Confirma que el prompt muestra `(.venv)` antes de seguir. En VS Code, `Ctrl+Shift+P` → *Python: Select Interpreter* → el de `.venv`.

**3. Instalar dependencias:**

```
pip install django psycopg[binary] dj-database-url django-environ whitenoise gunicorn django-htmx django-crispy-forms crispy-bootstrap5 django-simple-history openpyxl
pip freeze > requirements.txt
```

WeasyPrint se deja para la Fase 4; en Windows necesita GTK y no vale la pena pelear con eso ahora.

**4. Crear el proyecto Django con la estructura definitiva:**

```
django-admin startproject config .
python manage.py startapp core
python manage.py startapp academico
python manage.py startapp ingresos
python manage.py startapp gastos
python manage.py startapp cambio
python manage.py startapp reportes
```

Luego conviertes `config/settings.py` en el paquete `config/settings/` con `base.py`, `local.py` y `production.py`, y `__init__.py` vacío.

**5. Archivos de entorno.** Un `.env` local (que nunca se sube) y un `.env.example` (que sí):

```
SECRET_KEY=cambiar-esto
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=postgresql://usuario:clave@host/edumia?sslmode=require
TIME_ZONE=America/Caracas
LANGUAGE_CODE=es-ve
```

Y un `.gitignore` con al menos `.venv/`, `.env`, `__pycache__/`, `*.sqlite3`, `staticfiles/`, `.vscode/`.

**6. Crear la base de datos en Neon.** Entra a neon.com, crea cuenta con GitHub, un proyecto llamado `edumia`, región la más cercana (`us-east`). Copia el connection string en `DATABASE_URL`. Conserva `?sslmode=require` — sin eso la conexión falla.

Conviene crear dos ramas en Neon desde el inicio: `main` para producción y `dev` para tu máquina. Es gratis y evita que una migración a medias toque los datos reales.

**7. Primera migración y superusuario:**

```
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abre `http://127.0.0.1:8000/admin/` y entra. Si llegaste aquí, Django y Neon están conversando.

**8. Repositorio en GitHub:**

```
git init
git add .
git commit -m "Fase 0: esqueleto del proyecto"
git branch -M main
git remote add origin https://github.com/<tu-usuario>/edumia.git
git push -u origin main
```

**9. Desplegar en Koyeb.** Crea cuenta con GitHub en koyeb.com, *Create Web Service* → GitHub → el repo `edumia`. Configura:

| Campo | Valor |
| --- | --- |
| Builder | Buildpack (detecta Python solo) |
| Build command | `pip install -r requirements.txt && python manage.py collectstatic --noinput` |
| Run command | `python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` |
| Instance | Free |
| Health check | Ruta `/salud/` |

Variables de entorno en Koyeb: las mismas del `.env` pero con `DEBUG=False`, el `ALLOWED_HOSTS` del dominio que te asigne, `DJANGO_SETTINGS_MODULE=config.settings.production` y `CSRF_TRUSTED_ORIGINS=https://<tu-dominio>.koyeb.app`.

**10. Verificaciones de cierre de Fase 0:**

- [ ] La URL pública responde y el admin abre con HTTPS
- [ ] `python manage.py check --deploy` no reporta advertencias críticas
- [ ] Un `git push` dispara el redespliegue automático
- [ ] La vista `/salud/` responde 200 sin tocar la base de datos
- [ ] `docs/ESTADO.md` y `docs/DECISIONES.md` creados con la decisión de hosting

Un consejo de flujo: no pases a la Fase 1 sin que el despliegue automático funcione. Arreglar el despliegue con quince modelos encima es mucho más difícil que con un "hola mundo".
