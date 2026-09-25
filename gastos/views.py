from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView

from core.auditoria import registrar
from core.mixins import RolRequeridoMixin, requiere_rol
from core.models import RegistroAuditoria
from core.utils import eliminar_protegido

from .forms import (
    CategoriaGastoForm,
    DetalleGastoFormSet,
    FondoForm,
    GastoForm,
    ProductoForm,
    ProveedorForm,
    TransferenciaFondoForm,
    UnidadMedidaForm,
)
from .models import CategoriaGasto, Fondo, Gasto, Producto, Proveedor, TransferenciaFondo, UnidadMedida
from .services import saldo_fondo

# Quién registra un gasto (además del superusuario).
ROLES_REGISTRO = ("administrador", "responsable_fondo")

# Quién aprueba/anula (docs/MODELOS_gastos.md: "Admin").
ROLES_APROBACION = ("administrador",)

# Quién administra los catálogos de Gastos desde Configuración.
ROLES_CONFIGURACION = ("administrador",)

# Quién puede mover dinero entre fondos (D-36): solo administrador, mismo
# rol que ya crea/edita fondos y ajusta el saldo inicial (D-32).
ROLES_TRANSFERENCIAS = ("administrador",)

# Quién puede ver el historial completo de gastos (cualquier estado):
# además de quienes registran/aprueban, se suman director y auditor, que
# ya tienen acceso de solo consulta a Reportes y balance.
ROLES_HISTORIAL = ("administrador", "responsable_fondo", "director", "auditor")


def _mensajes_error(e):
    return " ".join(e.messages)


@requiere_rol(*ROLES_REGISTRO)
def gasto_registrar(request):
    if request.method == "POST":
        form = GastoForm(request.POST, usuario=request.user)
        formset = DetalleGastoFormSet(request.POST, instance=Gasto(), prefix="renglones")
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                gasto = form.save(commit=False)
                gasto.registrado_por = request.user
                gasto.fecha_registro = timezone.now()
                gasto.tasa_aplicada = gasto.tasa.valor
                gasto.monto = gasto.monto_ves = gasto.monto_usd = 0
                gasto.save()
                formset.instance = gasto
                formset.save()
                gasto.recalcular()
            messages.success(request, f"Gasto #{gasto.pk} registrado. Queda pendiente de aprobación.")
            return redirect("gastos:gasto_detalle", pk=gasto.pk)
    else:
        form = GastoForm(usuario=request.user)
        formset = DetalleGastoFormSet(instance=Gasto(), prefix="renglones")
    return render(request, "gastos/gasto_form.html", {"form": form, "formset": formset})


@requiere_rol(*ROLES_REGISTRO)
def gasto_editar(request, pk):
    gasto = get_object_or_404(Gasto, pk=pk)
    if gasto.estado != Gasto.Estado.REGISTRADO:
        raise PermissionDenied("Solo se puede editar un gasto mientras está «registrado» (G-6).")

    if request.method == "POST":
        form = GastoForm(request.POST, instance=gasto, usuario=request.user)
        formset = DetalleGastoFormSet(request.POST, instance=gasto, prefix="renglones")
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                gasto = form.save(commit=False)
                gasto.tasa_aplicada = gasto.tasa.valor
                gasto.save()
                formset.instance = gasto
                formset.save()
                gasto.recalcular()
            messages.success(request, f"Gasto #{gasto.pk} actualizado.")
            return redirect("gastos:gasto_detalle", pk=gasto.pk)
    else:
        form = GastoForm(instance=gasto, usuario=request.user)
        formset = DetalleGastoFormSet(instance=gasto, prefix="renglones")
    return render(request, "gastos/gasto_form.html", {"form": form, "formset": formset, "gasto": gasto})


def gasto_renglon_nuevo(request):
    """HTMX: agrega un renglón vacío más al formset (fila `total`, tomado
    del TOTAL_FORMS actual en el navegador) y, en la misma respuesta, el
    TOTAL_FORMS actualizado (out-of-band) para que Django sepa procesarla
    al enviar el formulario."""
    total = int(request.GET.get("total", 0))
    formset_vacio = DetalleGastoFormSet(instance=Gasto(), prefix="renglones")
    formulario = formset_vacio.empty_form
    formulario.prefix = f"renglones-{total}"
    return render(request, "gastos/_renglon_nuevo_respuesta.html", {"form": formulario, "total": total})


@requiere_rol(*ROLES_APROBACION, *ROLES_REGISTRO)
def gasto_bandeja(request):
    gastos = (
        Gasto.objects.filter(estado=Gasto.Estado.REGISTRADO)
        .select_related("fondo", "proveedor", "registrado_por")
        .order_by("-fecha")
    )
    puede_aprobar = request.user.is_superuser or getattr(
        getattr(request.user, "perfilusuario", None), "rol", None
    ) in ROLES_APROBACION
    return render(request, "gastos/gasto_bandeja.html", {"gastos": gastos, "puede_aprobar": puede_aprobar})


@requiere_rol(*ROLES_HISTORIAL)
def gasto_detalle(request, pk):
    gasto = get_object_or_404(
        Gasto.objects.select_related("fondo", "proveedor", "registrado_por", "aprobado_por", "anulado_por"),
        pk=pk,
    )
    saldo_ves, saldo_usd = saldo_fondo(gasto.fondo)
    puede_aprobar = request.user.is_superuser or getattr(
        getattr(request.user, "perfilusuario", None), "rol", None
    ) in ROLES_APROBACION
    return render(request, "gastos/gasto_detalle.html", {
        "gasto": gasto,
        "renglones": gasto.renglones.select_related("producto__categoria", "categoria", "unidad"),
        "saldo_ves": saldo_ves,
        "saldo_usd": saldo_usd,
        "puede_aprobar": puede_aprobar,
        "puede_editar": gasto.estado == Gasto.Estado.REGISTRADO,
    })


@requiere_rol(*ROLES_APROBACION)
def gasto_aprobar(request, pk):
    gasto = get_object_or_404(Gasto, pk=pk)
    saldo_ves, saldo_usd = saldo_fondo(gasto.fondo)
    saldo_ves_proyectado = saldo_ves - gasto.monto_ves
    saldo_usd_proyectado = saldo_usd - gasto.monto_usd

    if request.method == "POST":
        gasto.autoaprobacion_confirmada = request.POST.get("autoaprobacion_confirmada") == "on"
        gasto.saldo_negativo_confirmado = request.POST.get("saldo_negativo_confirmado") == "on"
        try:
            gasto.transicionar(Gasto.Estado.APROBADO, request.user)
            registrar(request, RegistroAuditoria.Accion.APROBAR, modelo="Gasto", objeto_id=gasto.pk, descripcion=str(gasto))
            messages.success(request, f"Gasto #{gasto.pk} aprobado.")
            return redirect("gastos:gasto_bandeja")
        except ValidationError as e:
            messages.error(request, _mensajes_error(e))

    return render(request, "gastos/gasto_confirmar_aprobacion.html", {
        "gasto": gasto,
        "saldo_ves_proyectado": saldo_ves_proyectado,
        "saldo_usd_proyectado": saldo_usd_proyectado,
        "mismo_registrador": gasto.registrado_por_id == request.user.id,
    })


@requiere_rol(*ROLES_APROBACION)
def gasto_anular(request, pk):
    gasto = get_object_or_404(Gasto, pk=pk)
    if request.method == "POST":
        motivo = request.POST.get("motivo", "").strip()
        try:
            gasto.transicionar(Gasto.Estado.ANULADO, request.user, motivo=motivo)
            registrar(request, RegistroAuditoria.Accion.ANULAR, modelo="Gasto", objeto_id=gasto.pk, descripcion=motivo)
            messages.success(request, f"Gasto #{gasto.pk} anulado.")
            return redirect("gastos:gasto_bandeja")
        except ValidationError as e:
            messages.error(request, _mensajes_error(e))
    return render(request, "gastos/gasto_motivo.html", {
        "gasto": gasto, "titulo": "Anular gasto", "boton": "Anular gasto",
    })


class GastoListView(RolRequeridoMixin, ListView):
    """Historial completo de gastos en cualquier estado, con filtro por
    estado y búsqueda libre. La bandeja (`gasto_bandeja`) solo muestra los
    «registrado» a la espera de aprobación; esta pantalla sirve para
    ubicar cualquier gasto ya aprobado o anulado."""

    roles_permitidos = ROLES_HISTORIAL
    model = Gasto
    template_name = "gastos/gasto_lista.html"
    context_object_name = "gastos"
    paginate_by = 40

    def get_queryset(self):
        qs = Gasto.objects.select_related("fondo", "proveedor", "registrado_por")
        estado = self.request.GET.get("estado", "").strip()
        if estado:
            qs = qs.filter(estado=estado)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(proveedor__nombre__icontains=q)
                | Q(numero_documento__icontains=q)
                | Q(fondo__nombre__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["estados"] = Gasto.Estado.choices
        ctx["estado_filtro"] = self.request.GET.get("estado", "")
        ctx["q"] = self.request.GET.get("q", "")
        return ctx


# --- Configuración: catálogos de Gastos (rol administrador) ----------------

class CategoriaGastoListView(RolRequeridoMixin, ListView):
    roles_permitidos = ROLES_CONFIGURACION
    model = CategoriaGasto
    template_name = "gastos/categoria_lista.html"
    context_object_name = "categorias"
    queryset = CategoriaGasto.objects.select_related("fondo").order_by("nombre")


class CategoriaGastoCreateView(RolRequeridoMixin, CreateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = CategoriaGasto
    form_class = CategoriaGastoForm
    template_name = "gastos/categoria_form.html"
    success_url = reverse_lazy("gastos:categoria_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Categoría de gasto «{self.object}» creada.")
        return respuesta


class CategoriaGastoUpdateView(RolRequeridoMixin, UpdateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = CategoriaGasto
    form_class = CategoriaGastoForm
    template_name = "gastos/categoria_form.html"
    success_url = reverse_lazy("gastos:categoria_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Categoría de gasto «{self.object}» actualizada.")
        return respuesta


@requiere_rol(*ROLES_CONFIGURACION)
def categoria_eliminar(request, pk):
    categoria = get_object_or_404(CategoriaGasto, pk=pk)
    if request.method == "POST":
        return eliminar_protegido(request, categoria, "gastos:categoria_lista")
    return redirect("gastos:categoria_lista")


class UnidadMedidaListView(RolRequeridoMixin, ListView):
    roles_permitidos = ROLES_CONFIGURACION
    model = UnidadMedida
    template_name = "gastos/unidad_lista.html"
    context_object_name = "unidades"
    queryset = UnidadMedida.objects.order_by("nombre")


class UnidadMedidaCreateView(RolRequeridoMixin, CreateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = UnidadMedida
    form_class = UnidadMedidaForm
    template_name = "gastos/unidad_form.html"
    success_url = reverse_lazy("gastos:unidad_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Unidad de medida «{self.object}» creada.")
        return respuesta


class UnidadMedidaUpdateView(RolRequeridoMixin, UpdateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = UnidadMedida
    form_class = UnidadMedidaForm
    template_name = "gastos/unidad_form.html"
    success_url = reverse_lazy("gastos:unidad_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Unidad de medida «{self.object}» actualizada.")
        return respuesta


@requiere_rol(*ROLES_CONFIGURACION)
def unidad_eliminar(request, pk):
    unidad = get_object_or_404(UnidadMedida, pk=pk)
    if request.method == "POST":
        return eliminar_protegido(request, unidad, "gastos:unidad_lista")
    return redirect("gastos:unidad_lista")


class ProductoListView(RolRequeridoMixin, ListView):
    roles_permitidos = ROLES_CONFIGURACION
    model = Producto
    template_name = "gastos/producto_lista.html"
    context_object_name = "productos"
    queryset = Producto.objects.select_related("categoria", "unidad_default").order_by("nombre")


class ProductoCreateView(RolRequeridoMixin, CreateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = Producto
    form_class = ProductoForm
    template_name = "gastos/producto_form.html"
    success_url = reverse_lazy("gastos:producto_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Producto «{self.object}» creado.")
        return respuesta


class ProductoUpdateView(RolRequeridoMixin, UpdateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = Producto
    form_class = ProductoForm
    template_name = "gastos/producto_form.html"
    success_url = reverse_lazy("gastos:producto_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Producto «{self.object}» actualizado.")
        return respuesta


@requiere_rol(*ROLES_CONFIGURACION)
def producto_eliminar(request, pk):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == "POST":
        return eliminar_protegido(request, producto, "gastos:producto_lista")
    return redirect("gastos:producto_lista")


class ProveedorListView(RolRequeridoMixin, ListView):
    roles_permitidos = ROLES_CONFIGURACION
    model = Proveedor
    template_name = "gastos/proveedor_lista.html"
    context_object_name = "proveedores"
    queryset = Proveedor.objects.order_by("nombre")


class ProveedorCreateView(RolRequeridoMixin, CreateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = Proveedor
    form_class = ProveedorForm
    template_name = "gastos/proveedor_form.html"
    success_url = reverse_lazy("gastos:proveedor_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Proveedor «{self.object}» creado.")
        return respuesta


class ProveedorUpdateView(RolRequeridoMixin, UpdateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = Proveedor
    form_class = ProveedorForm
    template_name = "gastos/proveedor_form.html"
    success_url = reverse_lazy("gastos:proveedor_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Proveedor «{self.object}» actualizado.")
        return respuesta


@requiere_rol(*ROLES_CONFIGURACION)
def proveedor_eliminar(request, pk):
    proveedor = get_object_or_404(Proveedor, pk=pk)
    if request.method == "POST":
        return eliminar_protegido(request, proveedor, "gastos:proveedor_lista")
    return redirect("gastos:proveedor_lista")


class FondoListView(RolRequeridoMixin, ListView):
    """Fase 8 (D-32): antes un fondo solo se podía crear desde /admin/ (y su
    saldo inicial no existía como concepto — el saldo siempre arrancaba en
    cero). Muestra el saldo actual de cada uno con `saldo_fondo()`, el mismo
    cálculo que usa el dashboard y los reportes."""

    roles_permitidos = ROLES_CONFIGURACION
    model = Fondo
    template_name = "gastos/fondo_lista.html"
    context_object_name = "fondos"
    queryset = Fondo.objects.order_by("-es_general", "nombre")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Tupla (fondo, saldo_ves, saldo_usd) en vez de un dict aparte: la
        # plantilla no puede indexar un dict por una variable sin un filtro
        # propio, así que es más simple traerlo ya emparejado.
        ctx["filas"] = [(fondo, *saldo_fondo(fondo)) for fondo in ctx["fondos"]]
        return ctx


class FondoCreateView(RolRequeridoMixin, CreateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = Fondo
    form_class = FondoForm
    template_name = "gastos/fondo_form.html"
    success_url = reverse_lazy("gastos:fondo_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        registrar(
            self.request, RegistroAuditoria.Accion.CREAR_FONDO,
            modelo="Fondo", objeto_id=self.object.pk, descripcion=str(self.object),
        )
        messages.success(self.request, f"Fondo «{self.object}» creado.")
        return respuesta


class FondoUpdateView(RolRequeridoMixin, UpdateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = Fondo
    form_class = FondoForm
    template_name = "gastos/fondo_form.html"
    success_url = reverse_lazy("gastos:fondo_lista")

    def form_valid(self, form):
        saldo_cambio = (
            "saldo_inicial_ves" in form.changed_data or "saldo_inicial_usd" in form.changed_data
        )
        # Ojo: form.instance (== self.object) ya trae los valores NUEVOS acá
        # (ModelForm los aplica durante full_clean, antes de form_valid), así
        # que el "antes" se consulta aparte, directo a la base de datos.
        anteriores = (
            Fondo.objects.filter(pk=self.object.pk)
            .values_list("saldo_inicial_ves", "saldo_inicial_usd")
            .first()
            if saldo_cambio else None
        )
        respuesta = super().form_valid(form)
        if saldo_cambio:
            registrar(
                self.request, RegistroAuditoria.Accion.AJUSTAR_SALDO_FONDO,
                modelo="Fondo", objeto_id=self.object.pk,
                descripcion=(
                    f"{self.object} — de Bs.{anteriores[0]}/USD.{anteriores[1]} "
                    f"a Bs.{self.object.saldo_inicial_ves}/USD.{self.object.saldo_inicial_usd}"
                ),
            )
        messages.success(self.request, f"Fondo «{self.object}» actualizado.")
        return respuesta


# --- Transferencias entre fondos (D-36) -------------------------------------

class TransferenciaFondoListView(RolRequeridoMixin, ListView):
    roles_permitidos = ROLES_TRANSFERENCIAS
    model = TransferenciaFondo
    template_name = "gastos/transferencia_lista.html"
    context_object_name = "transferencias"
    paginate_by = 40
    queryset = TransferenciaFondo.objects.select_related(
        "fondo_origen", "fondo_destino", "registrado_por", "anulado_por",
    )


@requiere_rol(*ROLES_TRANSFERENCIAS)
def transferencia_registrar(request):
    """El formulario solo junta los datos; toda la validación real (fondos
    distintos, saldo del origen) vive en `TransferenciaFondo.clean()`, así
    que si algo falla, `form.is_valid()` ya trae el mensaje listo — no hace
    falta capturar nada aparte acá."""
    if request.method == "POST":
        form = TransferenciaFondoForm(request.POST)
        if form.is_valid():
            transferencia = form.save(commit=False)
            transferencia.registrado_por = request.user
            transferencia.estado = TransferenciaFondo.Estado.REGISTRADA
            transferencia.save()
            registrar(
                request, RegistroAuditoria.Accion.TRANSFERIR_FONDO,
                modelo="TransferenciaFondo", objeto_id=transferencia.pk, descripcion=str(transferencia),
            )
            messages.success(request, f"Transferencia registrada: {transferencia}.")
            return redirect("gastos:transferencia_lista")
    else:
        form = TransferenciaFondoForm(initial={"fecha": timezone.now().date()})
    return render(request, "gastos/transferencia_form.html", {"form": form})


@requiere_rol(*ROLES_TRANSFERENCIAS)
def transferencia_anular(request, pk):
    transferencia = get_object_or_404(TransferenciaFondo, pk=pk)
    if request.method == "POST":
        motivo = request.POST.get("motivo", "").strip()
        try:
            transferencia.transicionar(TransferenciaFondo.Estado.ANULADA, request.user, motivo=motivo)
            registrar(
                request, RegistroAuditoria.Accion.ANULAR,
                modelo="TransferenciaFondo", objeto_id=transferencia.pk, descripcion=motivo,
            )
            messages.success(request, f"Transferencia «{transferencia}» anulada.")
            return redirect("gastos:transferencia_lista")
        except ValidationError as e:
            messages.error(request, _mensajes_error(e))
    return render(request, "gastos/transferencia_motivo.html", {
        "transferencia": transferencia, "titulo": "Anular transferencia", "boton": "Anular transferencia",
    })
