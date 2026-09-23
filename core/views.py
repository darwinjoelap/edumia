from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from academico.models import Estudiante, Representante, Seccion
from core.models import Institucion, PeriodoEscolar


def salud(request):
    """Health check de la plataforma.

    Deliberadamente sin consultas a la base de datos ni sesión: debe
    responder aunque Neon esté suspendido y no puede despertarlo.
    """
    return HttpResponse("ok", content_type="text/plain")


@login_required
def inicio(request):
    """Dashboard: resumen del período activo y accesos rápidos por rol."""
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
    if perfil and perfil.rol == "docente" and not request.user.is_superuser:
        # El docente solo ve sus propias secciones en el tablero.
        secciones = secciones.filter(docente_responsable=request.user)

    contexto = {
        "institucion": institucion,
        "periodo_activo": periodo_activo,
        "estudiantes_activos": Estudiante.objects.filter(activo=True).count(),
        "representantes_activos": Representante.objects.filter(activo=True).count(),
        "secciones": secciones,
        "total_secciones": secciones.count(),
    }
    return render(request, "core/dashboard.html", contexto)
