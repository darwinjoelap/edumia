"""Señales que alimentan la bitácora de auditoría (Fase 8, D-28): login y
login fallido son los dos únicos eventos que no pasan por una vista propia
de Edumia (usan `django.contrib.auth.urls`), así que se enganchan aquí en
vez de en `ingresos`/`gastos`/`cambio`/`core` como el resto."""

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .auditoria import registrar
from .models import RegistroAuditoria


@receiver(user_logged_in)
def _bitacora_login(sender, request, user, **kwargs):
    registrar(
        request, RegistroAuditoria.Accion.LOGIN,
        modelo="User", objeto_id=user.pk, descripcion=user.get_username(),
    )


@receiver(user_login_failed)
def _bitacora_login_fallido(sender, credentials, request=None, **kwargs):
    usuario_intentado = credentials.get("username", "") if credentials else ""
    registrar(
        request, RegistroAuditoria.Accion.LOGIN_FALLIDO,
        modelo="User", descripcion=f"Usuario intentado: {usuario_intentado}",
    )
