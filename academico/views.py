from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView

from core.mixins import verificar_seccion_docente
from core.models import PeriodoEscolar

from .forms import (
    EstudianteEditForm,
    ImportarArchivoForm,
    PromocionForm,
    RepresentanteForm,
    VinculoRepresentanteForm,
    construir_formset_alta_rapida,
)
from .importacion import validar_archivo
from .models import Estudiante, EstudianteRepresentante, Grado, Inscripcion, Representante, Seccion
from .promocion import calcular_plan, ejecutar_promocion

FILAS_POR_DEFECTO = 10
FILAS_MAXIMO = 50


@login_required
def alta_rapida_seccion(request, seccion_id):
    """D-20: alta rápida de varios estudiantes a la vez para una sección.

    Un docente solo puede usarla en la sección de la que es responsable
    (Fase 2); los demás roles con acceso a esta vista no se restringen aquí.
    """
    seccion = get_object_or_404(Seccion, pk=seccion_id)
    verificar_seccion_docente(request, seccion)
    periodo_activo = PeriodoEscolar.objects.filter(activo=True).first()

    try:
        filas = min(int(request.GET.get("filas", FILAS_POR_DEFECTO)), FILAS_MAXIMO)
    except ValueError:
        filas = FILAS_POR_DEFECTO
    filas = max(filas, 1)
    FormSet = construir_formset_alta_rapida(filas=filas)

    if request.method == "POST":
        formset = FormSet(request.POST)
        if not periodo_activo:
            messages.error(
                request,
                "No hay un período escolar activo. Actívalo en /admin/ antes de continuar.",
            )
        elif formset.is_valid():
            creados = 0
            hubo_error = False
            for form in formset:
                if form.fila_vacia():
                    continue
                try:
                    with transaction.atomic():
                        estudiante = form.save()
                        Inscripcion.objects.create(
                            estudiante=estudiante,
                            seccion=seccion,
                            periodo=periodo_activo,
                            fecha=timezone.localdate(),
                        )
                    creados += 1
                except IntegrityError:
                    # Defensa adicional ante una carrera entre dos envíos
                    # simultáneos; el caso normal ya lo atrapa el formset.
                    hubo_error = True
                    form.add_error("cedula_escolar", "Ya existe un estudiante con esta cédula.")

            if creados:
                messages.success(request, f"{creados} estudiante(s) inscrito(s) en {seccion}.")
            if not creados and not hubo_error:
                messages.info(request, "No se cargó ningún estudiante (todas las filas estaban vacías).")
            if not hubo_error:
                return redirect("academico:alta_rapida_seccion", seccion_id=seccion.pk)
    else:
        formset = FormSet()

    return render(
        request,
        "academico/alta_rapida.html",
        {
            "seccion": seccion,
            "formset": formset,
            "periodo_activo": periodo_activo,
            "filas": filas,
        },
    )


def _clave_sesion_importacion(seccion_id):
    return f"academico_import_estudiantes_{seccion_id}"


@login_required
def importar_estudiantes_seccion(request, seccion_id):
    """D-20 (importación): sube un .xlsx/.csv, valida todo en un paso de
    vista previa (sin tocar la base de datos) y solo guarda si se confirma.
    Un docente solo puede usarla en su propia sección (Fase 2).
    """
    seccion = get_object_or_404(Seccion, pk=seccion_id)
    verificar_seccion_docente(request, seccion)
    periodo_activo = PeriodoEscolar.objects.filter(activo=True).first()
    clave_sesion = _clave_sesion_importacion(seccion_id)

    if request.method == "POST" and "cancelar" in request.POST:
        request.session.pop(clave_sesion, None)
        return redirect("academico:importar_estudiantes_seccion", seccion_id=seccion.pk)

    if request.method == "POST" and "confirmar" in request.POST:
        datos_sesion = request.session.get(clave_sesion)
        if not datos_sesion:
            messages.error(request, "La vista previa expiró o ya se usó. Vuelve a subir el archivo.")
            return redirect("academico:importar_estudiantes_seccion", seccion_id=seccion.pk)
        if not periodo_activo:
            messages.error(request, "No hay un período escolar activo. Actívalo en /admin/ antes de continuar.")
            return redirect("academico:importar_estudiantes_seccion", seccion_id=seccion.pk)

        creados = 0
        con_error = False
        for fila in datos_sesion["filas_validas"]:
            try:
                with transaction.atomic():
                    estudiante = Estudiante.objects.create(
                        nombres=fila["nombres"],
                        apellidos=fila["apellidos"],
                        fecha_nacimiento=fila["fecha_nacimiento"],
                        sexo=fila["sexo"],
                        cedula_escolar=fila["cedula_escolar"] or None,
                    )
                    Inscripcion.objects.create(
                        estudiante=estudiante,
                        seccion=seccion,
                        periodo=periodo_activo,
                        fecha=timezone.localdate(),
                    )
                creados += 1
            except IntegrityError:
                con_error = True  # carrera con otro envío simultáneo; caso raro

        request.session.pop(clave_sesion, None)
        if creados:
            messages.success(request, f"{creados} estudiante(s) importado(s) en {seccion}.")
        if con_error:
            messages.warning(
                request,
                "Alguna fila no se pudo guardar (posible duplicado creado mientras tanto). "
                "Revisa el listado de estudiantes.",
            )
        return redirect("academico:alta_rapida_seccion", seccion_id=seccion.pk)

    if request.method == "POST" and request.FILES.get("archivo"):
        form = ImportarArchivoForm(request.POST, request.FILES)
        if form.is_valid():
            filas_validas, filas_error, columnas_faltantes = validar_archivo(form.cleaned_data["archivo"])
            if columnas_faltantes:
                messages.error(
                    request,
                    "Faltan columnas obligatorias en el archivo: " + ", ".join(columnas_faltantes) + ".",
                )
                return render(request, "academico/importar_estudiantes_subir.html", {
                    "seccion": seccion, "form": form, "periodo_activo": periodo_activo,
                })
            request.session[clave_sesion] = {
                "filas_validas": filas_validas,
                "total_error": len(filas_error),
            }
            return render(request, "academico/importar_estudiantes_preview.html", {
                "seccion": seccion,
                "periodo_activo": periodo_activo,
                "filas_validas": filas_validas,
                "filas_error": filas_error,
                "recuperado_de_sesion": False,
            })
        return render(request, "academico/importar_estudiantes_subir.html", {
            "seccion": seccion, "form": form, "periodo_activo": periodo_activo,
        })

    # GET normal, o volver a esta URL con una vista previa aún pendiente en sesión.
    datos_sesion = request.session.get(clave_sesion)
    if datos_sesion:
        return render(request, "academico/importar_estudiantes_preview.html", {
            "seccion": seccion,
            "periodo_activo": periodo_activo,
            "filas_validas": datos_sesion["filas_validas"],
            "filas_error": [],
            "recuperado_de_sesion": True,
            "total_error_sesion": datos_sesion.get("total_error", 0),
        })

    form = ImportarArchivoForm()
    return render(request, "academico/importar_estudiantes_subir.html", {
        "seccion": seccion, "form": form, "periodo_activo": periodo_activo,
    })


# --- Representantes (CRUD) -------------------------------------------------
# "Eliminar" es desactivar (activo=False), no borrado físico (consistente
# con D-09: en Edumia nada se borra de verdad). Sin restricción de rol
# todavía (llega en la Fase 2).

def _filtrar_por_estado(qs, estado):
    if estado == "inactivos":
        return qs.filter(activo=False)
    if estado == "todos":
        return qs
    return qs.filter(activo=True)


class RepresentanteListView(LoginRequiredMixin, ListView):
    model = Representante
    template_name = "academico/representante_lista.html"
    context_object_name = "representantes"
    paginate_by = 25

    def get_queryset(self):
        qs = Representante.objects.order_by("apellidos", "nombres")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(nombres__icontains=q)
                | Q(apellidos__icontains=q)
                | Q(cedula__icontains=q)
                | Q(telefono__icontains=q)
            )
        return _filtrar_por_estado(qs, self.request.GET.get("estado", "activos"))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        ctx["estado"] = self.request.GET.get("estado", "activos")
        return ctx


class RepresentanteCreateView(LoginRequiredMixin, CreateView):
    model = Representante
    form_class = RepresentanteForm
    template_name = "academico/representante_form.html"

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Representante {self.object} creado.")
        return respuesta

    def get_success_url(self):
        return reverse("academico:representante_detalle", args=[self.object.pk])


class RepresentanteUpdateView(LoginRequiredMixin, UpdateView):
    model = Representante
    form_class = RepresentanteForm
    template_name = "academico/representante_form.html"

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Representante {self.object} actualizado.")
        return respuesta

    def get_success_url(self):
        return reverse("academico:representante_detalle", args=[self.object.pk])


@login_required
def representante_detalle(request, pk):
    representante = get_object_or_404(Representante, pk=pk)
    vinculos = representante.estudiantes.select_related("estudiante").order_by(
        "-es_principal", "estudiante__apellidos"
    )

    if request.method == "POST" and "agregar_vinculo" in request.POST:
        form_vinculo = VinculoRepresentanteForm(request.POST)
        if form_vinculo.is_valid():
            vinculo = form_vinculo.save(commit=False)
            vinculo.representante = representante
            try:
                vinculo.full_clean()
                vinculo.save()
            except ValidationError as error:
                for mensaje in error.messages:
                    form_vinculo.add_error(None, mensaje)
            else:
                messages.success(request, f"Vínculo con {vinculo.estudiante} agregado.")
                return redirect("academico:representante_detalle", pk=representante.pk)
    else:
        form_vinculo = VinculoRepresentanteForm()

    return render(request, "academico/representante_detalle.html", {
        "representante": representante,
        "vinculos": vinculos,
        "form_vinculo": form_vinculo,
    })


@login_required
def representante_toggle_activo(request, pk):
    representante = get_object_or_404(Representante, pk=pk)
    if request.method == "POST":
        representante.activo = not representante.activo
        representante.save(update_fields=["activo"])
        estado = "activado" if representante.activo else "desactivado"
        messages.success(request, f"Representante {estado}.")
    return redirect("academico:representante_detalle", pk=representante.pk)


@login_required
def vinculo_eliminar(request, pk, vinculo_id):
    representante = get_object_or_404(Representante, pk=pk)
    vinculo = get_object_or_404(EstudianteRepresentante, pk=vinculo_id, representante=representante)
    if request.method == "POST":
        estudiante = vinculo.estudiante
        vinculo.delete()
        messages.success(request, f"Se quitó el vínculo con {estudiante}.")
    return redirect("academico:representante_detalle", pk=representante.pk)


# --- Estudiantes (listar / ver / editar / activar) -------------------------
# La creación ya la cubren la alta rápida (D-20) y la importación; aquí solo
# falta el resto del CRUD. Mismo criterio de "eliminar" = desactivar.

class EstudianteListView(LoginRequiredMixin, ListView):
    model = Estudiante
    template_name = "academico/estudiante_lista.html"
    context_object_name = "estudiantes"
    paginate_by = 25

    def get_periodo_activo(self):
        if not hasattr(self, "_periodo_activo"):
            self._periodo_activo = PeriodoEscolar.objects.filter(activo=True).first()
        return self._periodo_activo

    def get_queryset(self):
        qs = Estudiante.objects.order_by("apellidos", "nombres")
        periodo_activo = self.get_periodo_activo()

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(nombres__icontains=q) | Q(apellidos__icontains=q) | Q(cedula_escolar__icontains=q)
            )

        seccion_id = self.request.GET.get("seccion")
        if seccion_id:
            qs = qs.filter(inscripciones__seccion_id=seccion_id, inscripciones__periodo=periodo_activo)

        nivel = self.request.GET.get("nivel")
        if nivel:
            qs = qs.filter(
                inscripciones__seccion__grado__nivel=nivel, inscripciones__periodo=periodo_activo
            )

        qs = _filtrar_por_estado(qs, self.request.GET.get("estado", "activos"))

        if periodo_activo:
            inscripciones_periodo_activo = Inscripcion.objects.filter(
                periodo=periodo_activo
            ).select_related("seccion", "seccion__grado")
            qs = qs.prefetch_related(
                Prefetch(
                    "inscripciones",
                    queryset=inscripciones_periodo_activo,
                    to_attr="inscripcion_periodo_activo_lista",
                )
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        periodo_activo = self.get_periodo_activo()
        ctx["q"] = self.request.GET.get("q", "")
        ctx["estado"] = self.request.GET.get("estado", "activos")
        ctx["seccion_id"] = self.request.GET.get("seccion", "")
        ctx["nivel"] = self.request.GET.get("nivel", "")
        ctx["periodo_activo"] = periodo_activo
        ctx["secciones"] = (
            Seccion.objects.filter(periodo=periodo_activo)
            .select_related("grado")
            .order_by("grado__orden", "nombre")
            if periodo_activo
            else Seccion.objects.none()
        )
        ctx["niveles"] = Grado.Nivel.choices
        return ctx


@login_required
def estudiante_detalle(request, pk):
    estudiante = get_object_or_404(Estudiante, pk=pk)
    representantes = estudiante.representantes.select_related("representante").order_by("-es_principal")
    inscripcion_actual = (
        estudiante.inscripciones.filter(periodo__activo=True).select_related("seccion", "periodo").first()
    )
    return render(request, "academico/estudiante_detalle.html", {
        "estudiante": estudiante,
        "representantes": representantes,
        "inscripcion_actual": inscripcion_actual,
    })


class EstudianteUpdateView(LoginRequiredMixin, UpdateView):
    model = Estudiante
    form_class = EstudianteEditForm
    template_name = "academico/estudiante_form.html"

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Estudiante {self.object} actualizado.")
        return respuesta

    def get_success_url(self):
        return reverse("academico:estudiante_detalle", args=[self.object.pk])


@login_required
def estudiante_toggle_activo(request, pk):
    estudiante = get_object_or_404(Estudiante, pk=pk)
    if request.method == "POST":
        estudiante.activo = not estudiante.activo
        estudiante.save(update_fields=["activo"])
        estado = "activado" if estudiante.activo else "desactivado"
        messages.success(request, f"Estudiante {estado}.")
    return redirect("academico:estudiante_detalle", pk=estudiante.pk)


# --- Promoción masiva al siguiente período ---------------------------------

_CLAVE_SESION_PROMOCION = "academico_promocion_periodo_destino"


@login_required
def promocion_masiva(request):
    periodo_origen = PeriodoEscolar.objects.filter(activo=True).first()
    if not periodo_origen:
        messages.error(request, "No hay un período escolar activo del cual promover.")
        return redirect("academico:estudiante_lista")

    if request.method == "POST" and "confirmar" in request.POST:
        periodo_destino = PeriodoEscolar.objects.filter(
            pk=request.session.get(_CLAVE_SESION_PROMOCION)
        ).first()
        if not periodo_destino:
            messages.error(request, "Selecciona de nuevo el período destino.")
            return redirect("academico:promocion_masiva")

        resultado = ejecutar_promocion(periodo_origen, periodo_destino, timezone.localdate())
        request.session.pop(_CLAVE_SESION_PROMOCION, None)
        messages.success(
            request,
            f"Promoción de {periodo_origen} a {periodo_destino}: "
            f"{resultado['promovidos']} promovido(s), {resultado['egresados']} egresado(s), "
            f"{resultado['ya_existian']} ya estaban promovidos, "
            f"{resultado['sin_destino']} sin sección destino (créala y vuelve a correr la promoción).",
        )
        return redirect("academico:promocion_masiva")

    if request.method == "POST":
        form = PromocionForm(request.POST, periodo_origen=periodo_origen)
        if form.is_valid():
            periodo_destino = form.cleaned_data["periodo_destino"]
            request.session[_CLAVE_SESION_PROMOCION] = periodo_destino.pk
            plan = calcular_plan(periodo_origen, periodo_destino)
            return render(request, "academico/promocion_preview.html", {
                "periodo_origen": periodo_origen,
                "periodo_destino": periodo_destino,
                "plan": plan,
            })
    else:
        form = PromocionForm(periodo_origen=periodo_origen)

    return render(request, "academico/promocion_form.html", {
        "periodo_origen": periodo_origen,
        "form": form,
    })
