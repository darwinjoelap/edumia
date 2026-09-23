"""Utilidades de control de acceso por rol (Fase 2).

El rol vive en PerfilUsuario.rol (core/models.py) y se sincroniza con los
Group de Django, pero estas utilidades leen el rol directamente del perfil
para no depender de que los nombres de Group coincidan con los valores del
choices en todos los casos. Un superusuario siempre pasa, sin importar el rol.
"""

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


def _rol_de(user):
    """Devuelve el rol (string) del usuario, o None si no tiene perfil."""
    perfil = getattr(user, "perfilusuario", None)
    if perfil is None:
        return None
    return perfil.rol


class RolRequeridoMixin(LoginRequiredMixin, UserPassesTestMixin):
    """CBV mixin: solo permite el acceso a usuarios con alguno de los roles
    listados en `roles_permitidos`. El superusuario siempre pasa."""

    roles_permitidos = ()

    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        return _rol_de(user) in self.roles_permitidos

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("No tienes el rol necesario para acceder a esta página.")


def requiere_rol(*roles):
    """Decorador para vistas basadas en función. Requiere login y que el rol
    del usuario esté entre `roles`. El superusuario siempre pasa."""

    from functools import wraps

    from django.contrib.auth.decorators import login_required

    def decorador(vista):
        @login_required
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_superuser and _rol_de(request.user) not in roles:
                raise PermissionDenied("No tienes el rol necesario para acceder a esta página.")
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador


def verificar_seccion_docente(request, seccion):
    """Si el usuario es docente (y no superusuario), verifica que `seccion`
    sea la sección de la que es docente_responsable. Lanza PermissionDenied
    si no lo es. Otros roles no se restringen aquí (eso lo maneja cada vista
    según lo que corresponda)."""
    user = request.user
    if user.is_superuser:
        return
    if _rol_de(user) != "docente":
        return
    if seccion.docente_responsable_id != user.id:
        raise PermissionDenied("Esta sección no está a tu cargo.")
