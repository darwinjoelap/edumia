from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView

from academico.models import Estudiante, Grado, Representante, Seccion
from core.mixins import RolRequeridoMixin, requiere_rol
from core.models import Institucion, PeriodoEscolar

from .forms import GradoForm, InstitucionForm, PeriodoEscolarForm

# Roles que manejan dinero (todos menos docente): ven el balance y los
# accesos de ingreso/gasto en el dashboard.
ROLES_FINANZAS = ("administrador", "responsable_fondo", "director", "auditor")

# Rol con control total sobre la configuración general (distinto del
# superusuario de Django, que sigue siendo el único con acceso a /admin/).
ROLES_CONFIGURACION = ("administrador",)


def salud(request):
    """Health check de la plataforma.

    Deliberadamente sin consultas a la base de datos ni sesión: debe
    responder aunque Neon esté suspendido y no puede despertarlo.
    """
    return HttpResponse("ok", content_type="text/plain")


@login_required
def inicio(request):
    """Dashboard: resumen del período activo, balance y accesos rápidos por rol."""
    periodo_activo = PeriodoEscolar.objects.filter(activo=True).first()
    institucion = Institucion.obtener()

    secciones = Seccion.objects.none()
    if periodo_activo:
        secciones = (
            Seccion.objects.filter(periodo=periodo_activo, activa=True)
            .select_related("grado", "docente_responsable")
            .order_by("grado__orden", "nombre")
        )

    perfil = getattr(request.user, "perfilusuario", None)
    rol = perfil.rol if perfil else None
    if rol == "docente" and not request.user.is_superuser:
        # El docente solo ve sus propias secciones en el tablero.
        secciones = secciones.filter(docente_responsable=request.user)

    puede_ver_finanzas = request.user.is_superuser or rol in ROLES_FINANZAS
    puede_configurar = request.user.is_superuser or rol in ROLES_CONFIGURACION

    contexto = {
        "institucion": institucion,
        "periodo_activo": periodo_activo,
        "estudiantes_activos": Estudiante.objects.filter(activo=True).count(),
        "representantes_activos": Representante.objects.filter(activo=True).count(),
        "secciones": secciones,
        "total_secciones": secciones.count(),
        "puede_ver_finanzas": puede_ver_finanzas,
        "puede_configurar": puede_configurar,
        # Todavía no existen los modelos de Ingreso/Gasto (Fase 3 y 5):
        # el balance se deja en cero, listo para calcularse de verdad
        # apenas esos módulos entren en producción.
        "balance": 0,
    }
    return render(request, "core/dashboard.html", contexto)


@login_required
def proximamente(request):
    """Pantalla de aviso para accesos a funciones que aún no se han construido
    (ingresos y gastos llegan en las Fases 3 y 5)."""
    return render(request, "core/proximamente.html", {
        "titulo": request.GET.get("titulo", "Próximamente"),
    })


# --- Configuración general (rol administrador o superusuario) --------------

@requiere_rol(*ROLES_CONFIGURACION)
def configuracion(request):
    return render(request, "core/configuracion/inicio.html", {
        "institucion": Institucion.obtener(),
        "total_grados": Grado.objects.count(),
        "total_periodos": PeriodoEscolar.objects.count(),
    })


class InstitucionUpdateView(RolRequeridoMixin, UpdateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = Institucion
    form_class = InstitucionForm
    template_name = "core/configuracion/institucion_form.html"
    success_url = reverse_lazy("core:configuracion")

    def get_object(self, queryset=None):
        return Institucion.obtener()

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, "Datos de la institución actualizados.")
        return respuesta


class GradoListView(RolRequeridoMixin, ListView):
    roles_permitidos = ROLES_CONFIGURACION
    model = Grado
    template_name = "core/configuracion/grado_lista.html"
    context_object_name = "grados"


class GradoCreateView(RolRequeridoMixin, CreateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = Grado
    form_class = GradoForm
    template_name = "core/configuracion/grado_form.html"
    success_url = reverse_lazy("core:grado_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Grado «{self.object}» creado.")
        return respuesta


class GradoUpdateView(RolRequeridoMixin, UpdateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = Grado
    form_class = GradoForm
    template_name = "core/configuracion/grado_form.html"
    success_url = reverse_lazy("core:grado_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Grado «{self.object}» actualizado.")
        return respuesta


@requiere_rol(*ROLES_CONFIGURACION)
def grado_eliminar(request, pk):
    grado = get_object_or_404(Grado, pk=pk)
    if request.method == "POST":
        if Seccion.objects.filter(grado=grado).exists():
            messages.error(
                request, f"No se puede eliminar «{grado}»: tiene secciones asociadas."
            )
        else:
            nombre = str(grado)
            grado.delete()
            messages.success(request, f"Grado «{nombre}» eliminado.")
    return redirect("core:grado_lista")


class PeriodoListView(RolRequeridoMixin, ListView):
    roles_permitidos = ROLES_CONFIGURACION
    model = PeriodoEscolar
    template_name = "core/configuracion/periodo_lista.html"
    context_object_name = "periodos"


class PeriodoCreateView(RolRequeridoMixin, CreateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = PeriodoEscolar
    form_class = PeriodoEscolarForm
    template_name = "core/configuracion/periodo_form.html"
    success_url = reverse_lazy("core:periodo_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Período «{self.object}» creado.")
        return respuesta


class PeriodoUpdateView(RolRequeridoMixin, UpdateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = PeriodoEscolar
    form_class = PeriodoEscolarForm
    template_name = "core/configuracion/periodo_form.html"
    success_url = reverse_lazy("core:periodo_lista")

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        messages.success(self.request, f"Período «{self.object}» actualizado.")
        return respuesta


@requiere_rol(*ROLES_CONFIGURACION)
def periodo_activar(request, pk):
    periodo = get_object_or_404(PeriodoEscolar, pk=pk)
    if request.method == "POST":
        if periodo.cerrado:
            messages.error(request, "No se puede activar un período cerrado.")
        else:
            with transaction.atomic():
                PeriodoEscolar.objects.filter(activo=True).exclude(pk=periodo.pk).update(activo=False)
                periodo.activo = True
                periodo.save(update_fields=["activo"])
            messages.success(request, f"Período «{periodo}» activado.")
    return redirect("core:periodo_lista")


@requiere_rol(*ROLES_CONFIGURACION)
def periodo_cerrar(request, pk):
    periodo = get_object_or_404(PeriodoEscolar, pk=pk)
    if request.method == "POST":
        periodo.cerrado = True
        periodo.activo = False
        periodo.cerrado_por = request.user
        periodo.fecha_cierre = timezone.now()
        periodo.save(update_fields=["cerrado", "activo", "cerrado_por", "fecha_cierre"])
        messages.success(request, f"Período «{periodo}» cerrado.")
    return redirect("core:periodo_lista")
