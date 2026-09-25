from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView

from core.mixins import RolRequeridoMixin, requiere_rol

from .forms import AporteForm, ConceptoIngresoForm, FormaPagoForm
from .models import Aporte, ConceptoIngreso, FormaPago

# Quiénes pueden registrar un aporte individual desde esta pantalla (además
# del superusuario, que siempre pasa). El registro en lote por sección, para
# el docente, es una pantalla aparte (todavía no construida).
ROLES_REGISTRO = ("administrador", "responsable_fondo")

# Quién verifica/observa/anula (docs/MODELOS_cambio_ingresos.md: "Admin").
ROLES_VERIFICACION = ("administrador",)

# Quién administra los catálogos de Ingresos desde Configuración (debe
# coincidir con core.views.ROLES_CONFIGURACION).
ROLES_CONFIGURACION = ("administrador",)


@requiere_rol(*ROLES_REGISTRO)
def aporte_registrar(request):
    """Registro individual de un aporte. Queda en estado «registrado»
    directamente (el flujo por «borrador» no lo usa todavía ninguna
    pantalla); el administrador lo verifica después desde la bandeja."""
    if request.method == "POST":
        form = AporteForm(request.POST)
        if form.is_valid():
            aporte = form.save(commit=False)
            aporte.registrado_por = request.user
            aporte.estado = Aporte.Estado.REGISTRADO
            aporte.fecha_registro = timezone.now()
            aporte.save()
            messages.success(
                request,
                f"Aporte de {aporte.monto} {aporte.moneda} registrado. Queda pendiente de verificación.",
            )
            return redirect("ingresos:aporte_registrar")
    else:
        form = AporteForm()
    return render(request, "ingresos/aporte_form.html", {"form": form})


@requiere_rol(*ROLES_VERIFICACION, *ROLES_REGISTRO)
def aporte_bandeja(request):
    """Bandeja de verificación: aportes «registrado» u «observado» a la
    espera de una decisión del administrador. Quien solo registra
    (ROLES_REGISTRO) también puede verla, para saber qué falta por revisar,
    pero solo el administrador tiene los botones de acción (ver plantilla)."""
    aportes = (
        Aporte.objects.filter(estado__in=[Aporte.Estado.REGISTRADO, Aporte.Estado.OBSERVADO])
        .select_related("concepto", "inscripcion__estudiante", "inscripcion__seccion__grado", "registrado_por")
        .order_by("-creado_en")
    )
    puede_verificar = request.user.is_superuser or getattr(
        getattr(request.user, "perfilusuario", None), "rol", None
    ) in ROLES_VERIFICACION
    return render(request, "ingresos/aporte_bandeja.html", {
        "aportes": aportes, "puede_verificar": puede_verificar,
    })


@requiere_rol(*ROLES_VERIFICACION)
def aporte_verificar(request, pk):
    aporte = get_object_or_404(Aporte, pk=pk)
    if request.method == "POST":
        try:
            aporte.transicionar(Aporte.Estado.VERIFICADO, request.user)
            messages.success(request, f"Aporte «{aporte}» verificado.")
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
    return redirect("ingresos:aporte_bandeja")


@requiere_rol(*ROLES_VERIFICACION)
def aporte_observar(request, pk):
    aporte = get_object_or_404(Aporte, pk=pk)
    if request.method == "POST":
        motivo = request.POST.get("motivo", "").strip()
        try:
            aporte.transicionar(Aporte.Estado.OBSERVADO, request.user, motivo=motivo)
            messages.success(request, f"Aporte «{aporte}» marcado como observado.")
            return redirect("ingresos:aporte_bandeja")
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
    return render(request, "ingresos/aporte_motivo.html", {
        "aporte": aporte, "accion": "observar", "titulo": "Observar aporte",
        "etiqueta_motivo": "Observación", "boton": "Marcar como observado",
    })


@requiere_rol(*ROLES_VERIFICACION)
def aporte_anular(request, pk):
    aporte = get_object_or_404(Aporte, pk=pk)
    if request.method == "POST":
        motivo = request.POST.get("motivo", "").strip()
        try:
            aporte.transicionar(Aporte.Estado.ANULADO, request.user, motivo=motivo)
            messages.success(request, f"Aporte «{aporte}» anulado.")
            return redirect("ingresos:aporte_bandeja")
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
    return render(request, "ingresos/aporte_motivo.html", {
        "aporte": aporte, "accion": "anular", "titulo": "Anular aporte",
        "etiqueta_motivo": "Motivo de anulación", "boton": "Anular aporte",
    })


# --- Configuración: catálogos de Ingresos (rol administrador) --------------

class ConceptoIngresoListView(RolRequeridoMixin, ListView):
    roles_permitidos = ROLES_CONFIGURACION
    model = ConceptoIngreso
    template_name = "ingresos/concepto_lista.html"
    context_object_name = "conceptos"
    queryset = ConceptoIngreso.objects.select_related("fondo").order_by("nombre")


class ConceptoIngresoCreateView(RolRequeridoMixin, CreateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = ConceptoIngreso
    form_class = ConceptoIngresoForm
    template_name = "ingresos/concepto_form.html"
    success_url = reverse_lazy("ingresos:concepto_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Concepto de ingreso «{self.object}» creado.")
        return respuesta


class ConceptoIngresoUpdateView(RolRequeridoMixin, UpdateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = ConceptoIngreso
    form_class = ConceptoIngresoForm
    template_name = "ingresos/concepto_form.html"
    success_url = reverse_lazy("ingresos:concepto_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Concepto de ingreso «{self.object}» actualizado.")
        return respuesta


class FormaPagoListView(RolRequeridoMixin, ListView):
    roles_permitidos = ROLES_CONFIGURACION
    model = FormaPago
    template_name = "ingresos/formapago_lista.html"
    context_object_name = "formas_pago"
    queryset = FormaPago.objects.order_by("nombre")


class FormaPagoCreateView(RolRequeridoMixin, CreateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = FormaPago
    form_class = FormaPagoForm
    template_name = "ingresos/formapago_form.html"
    success_url = reverse_lazy("ingresos:formapago_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Forma de pago «{self.object}» creada.")
        return respuesta


class FormaPagoUpdateView(RolRequeridoMixin, UpdateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = FormaPago
    form_class = FormaPagoForm
    template_name = "ingresos/formapago_form.html"
    success_url = reverse_lazy("ingresos:formapago_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Forma de pago «{self.object}» actualizada.")
        return respuesta
