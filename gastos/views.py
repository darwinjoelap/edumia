from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView

from core.mixins import RolRequeridoMixin, requiere_rol

from .forms import (
    CategoriaGastoForm,
    DetalleGastoFormSet,
    GastoForm,
    ProductoForm,
    ProveedorForm,
    UnidadMedidaForm,
)
from .models import CategoriaGasto, Gasto, Producto, Proveedor, UnidadMedida
from .services import saldo_fondo

# Quién registra un gasto (además del superusuario).
ROLES_REGISTRO = ("administrador", "responsable_fondo")

# Quién aprueba/anula (docs/MODELOS_gastos.md: "Admin").
ROLES_APROBACION = ("administrador",)

# Quién administra los catálogos de Gastos desde Configuración.
ROLES_CONFIGURACION = ("administrador",)


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


@requiere_rol(*ROLES_APROBACION, *ROLES_REGISTRO)
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
        "renglones": gasto.renglones.select_related("producto", "unidad"),
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
            messages.success(request, f"Gasto #{gasto.pk} anulado.")
            return redirect("gastos:gasto_bandeja")
        except ValidationError as e:
            messages.error(request, _mensajes_error(e))
    return render(request, "gastos/gasto_motivo.html", {
        "gasto": gasto, "titulo": "Anular gasto", "boton": "Anular gasto",
    })


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
