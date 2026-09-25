from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.html import format_html
from django.views.generic import CreateView, ListView, UpdateView

from academico.models import Inscripcion, Seccion
from core.mixins import RolRequeridoMixin, requiere_rol, verificar_seccion_docente
from core.models import PeriodoEscolar
from core.utils import normalizar_cedula, normalizar_telefono

from .forms import (
    AporteForm,
    AporteLoteEncabezadoForm,
    AporteLoteFormSet,
    ConceptoIngresoForm,
    FormaPagoForm,
    MontoConceptoForm,
)
from .models import Aporte, ConceptoIngreso, FormaPago, MontoConcepto

# Quiénes pueden registrar un aporte individual desde esta pantalla (además
# del superusuario, que siempre pasa). El registro en lote por sección, para
# el docente, es una pantalla aparte (ver aporte_registrar_lote).
ROLES_REGISTRO = ("administrador", "responsable_fondo")

# Quién verifica/observa/anula (docs/MODELOS_cambio_ingresos.md: "Admin").
ROLES_VERIFICACION = ("administrador",)

# Quién administra los catálogos de Ingresos desde Configuración (debe
# coincidir con core.views.ROLES_CONFIGURACION).
ROLES_CONFIGURACION = ("administrador",)

# Quién puede usar el registro en lote por sección, además del docente
# responsable de esa sección en particular (verificar_seccion_docente lo
# restringe a "la suya"; administrador/responsable_fondo pueden usarlo en
# cualquier sección).
ROLES_LOTE = (*ROLES_REGISTRO, "docente")


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


@requiere_rol(*ROLES_VERIFICACION, *ROLES_REGISTRO)
def aporte_buscar(request):
    """Búsqueda por referencia, cédula del titular o teléfono del emisor —
    los tres datos que alguien trae en la mano cuando reclama un pago
    ("¿ya registraron mi Pago Móvil con esta referencia?"). Normaliza la
    consulta igual que `Aporte.save()` normaliza lo guardado, para que
    puntos/guiones/espacios no rompan la coincidencia."""
    query = request.GET.get("q", "").strip()
    aportes = Aporte.objects.none()
    if query:
        cedula = normalizar_cedula(query) or ""
        telefono = normalizar_telefono(query)
        referencia = query.strip().upper()
        aportes = (
            Aporte.objects.filter(
                Q(referencia=referencia) | Q(cedula_titular=cedula) | Q(telefono_emisor=telefono)
            )
            .select_related("concepto", "inscripcion__estudiante", "registrado_por", "recibo")
            .order_by("-creado_en")
        )
    return render(request, "ingresos/aporte_buscar.html", {"query": query, "aportes": aportes})


@login_required
def aporte_registrar_lote(request, seccion_id):
    """Registro en lote (D-20, mismo patrón que la alta rápida de
    estudiantes): una fila por cada estudiante inscrito y activo en la
    sección, con un encabezado común (concepto, forma de pago, fecha,
    moneda, tasa). Una fila sin monto se ignora — significa que ese
    estudiante no pagó (todavía).

    El docente solo puede usarla en su propia sección
    (`verificar_seccion_docente`); administrador y responsable de fondo
    pueden usarla en cualquiera."""
    seccion = get_object_or_404(Seccion, pk=seccion_id)
    rol = getattr(getattr(request.user, "perfilusuario", None), "rol", None)
    if not request.user.is_superuser and rol not in ROLES_LOTE:
        raise PermissionDenied("No tienes permiso para registrar aportes en lote.")
    verificar_seccion_docente(request, seccion)

    periodo_activo = PeriodoEscolar.objects.filter(activo=True).first()
    inscripciones = list(
        Inscripcion.objects.filter(seccion=seccion, estado=Inscripcion.Estado.ACTIVO)
        .select_related("estudiante")
        .order_by("estudiante__apellidos", "estudiante__nombres")
    )
    if periodo_activo:
        inscripciones = [i for i in inscripciones if i.periodo_id == periodo_activo.pk]

    nombre_docente = request.user.get_full_name() or request.user.username

    if request.method == "POST":
        encabezado = AporteLoteEncabezadoForm(request.POST, entregado_por_inicial=nombre_docente)
        formset = AporteLoteFormSet(request.POST, initial=[{"inscripcion_id": i.pk} for i in inscripciones])
        if not periodo_activo:
            messages.error(request, "No hay un período escolar activo. Actívalo en Configuración antes de continuar.")
        elif encabezado.is_valid() and formset.is_valid():
            creados = 0
            hubo_error = False
            datos = encabezado.cleaned_data
            with transaction.atomic():
                for form, inscripcion in zip(formset, inscripciones):
                    if form.fila_vacia():
                        continue
                    aporte = Aporte(
                        inscripcion=inscripcion,
                        concepto=datos["concepto"],
                        concepto_libre=datos["concepto_libre"],
                        mes_cubierto=datos["mes_cubierto"],
                        monto=form.cleaned_data["monto"],
                        moneda=datos["moneda"],
                        tasa=datos["tasa"],
                        forma_pago=datos["forma_pago"],
                        fecha_pago=datos["fecha_pago"],
                        banco_destino=datos["banco_destino"],
                        referencia=form.cleaned_data.get("referencia", ""),
                        cedula_titular=form.cleaned_data.get("cedula_titular", ""),
                        telefono_emisor=form.cleaned_data.get("telefono_emisor", ""),
                        banco_origen=form.cleaned_data.get("banco_origen"),
                        entregado_por_nombre=datos["entregado_por_nombre"],
                        registrado_por=request.user,
                        estado=Aporte.Estado.REGISTRADO,
                        fecha_registro=timezone.now(),
                    )
                    try:
                        aporte.full_clean()
                        aporte.save()
                        creados += 1
                    except ValidationError as e:
                        hubo_error = True
                        mensajes = e.messages if hasattr(e, "messages") else [str(e)]
                        form.add_error(None, f"{inscripcion.estudiante}: {'; '.join(mensajes)}")

            if creados:
                messages.success(request, f"{creados} aporte(s) registrado(s) en {seccion}.")
            if not creados and not hubo_error:
                messages.info(request, "No se registró ningún aporte (todas las filas estaban vacías).")
            if not hubo_error:
                return redirect("ingresos:aporte_registrar_lote", seccion_id=seccion.pk)
    else:
        encabezado = AporteLoteEncabezadoForm(entregado_por_inicial=nombre_docente)
        formset = AporteLoteFormSet(initial=[{"inscripcion_id": i.pk} for i in inscripciones])

    filas = list(zip(inscripciones, formset))
    return render(request, "ingresos/aporte_registrar_lote.html", {
        "seccion": seccion, "encabezado": encabezado, "formset": formset,
        "filas": filas, "periodo_activo": periodo_activo,
    })


@requiere_rol(*ROLES_VERIFICACION)
def aporte_verificar(request, pk):
    aporte = get_object_or_404(Aporte, pk=pk)
    if request.method == "POST":
        try:
            aporte.transicionar(Aporte.Estado.VERIFICADO, request.user)
            recibo = getattr(aporte, "recibo", None)
            if recibo is not None:
                messages.success(request, format_html(
                    'Aporte «{}» verificado. Recibo <a href="{}">{}</a> emitido.',
                    aporte, reverse("recibos:recibo_detalle", args=[recibo.pk]), recibo.numero_texto,
                ))
            else:
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


class MontoConceptoListView(RolRequeridoMixin, ListView):
    roles_permitidos = ROLES_CONFIGURACION
    model = MontoConcepto
    template_name = "ingresos/montoconcepto_lista.html"
    context_object_name = "montos"
    queryset = MontoConcepto.objects.select_related("concepto", "grado", "periodo").order_by(
        "-periodo__fecha_inicio", "concepto__nombre", "grado__orden",
    )


class MontoConceptoCreateView(RolRequeridoMixin, CreateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = MontoConcepto
    form_class = MontoConceptoForm
    template_name = "ingresos/montoconcepto_form.html"
    success_url = reverse_lazy("ingresos:montoconcepto_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Monto «{self.object}» creado.")
        return respuesta


class MontoConceptoUpdateView(RolRequeridoMixin, UpdateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = MontoConcepto
    form_class = MontoConceptoForm
    template_name = "ingresos/montoconcepto_form.html"
    success_url = reverse_lazy("ingresos:montoconcepto_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Monto «{self.object}» actualizado.")
        return respuesta


@requiere_rol(*ROLES_CONFIGURACION)
def montoconcepto_eliminar(request, pk):
    monto = get_object_or_404(MontoConcepto, pk=pk)
    if request.method == "POST":
        descripcion = str(monto)
        monto.delete()
        messages.success(request, f"Monto «{descripcion}» eliminado.")
    return redirect("ingresos:montoconcepto_lista")
