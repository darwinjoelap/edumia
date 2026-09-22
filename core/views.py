from django.http import HttpResponse


def salud(request):
    """Health check de la plataforma.

    Deliberadamente sin consultas a la base de datos ni sesión: debe
    responder aunque Neon esté suspendido y no puede despertarlo.
    """
    return HttpResponse("ok", content_type="text/plain")


def inicio(request):
    """Portada provisional de la Fase 0 (se reemplaza en la Fase 2)."""
    return HttpResponse("Edumia — en construcción", content_type="text/plain; charset=utf-8")
