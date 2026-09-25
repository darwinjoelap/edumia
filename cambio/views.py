from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from core.auditoria import registrar
from core.mixins import RolRequeridoMixin
from core.models import RegistroAuditoria

from .forms import TasaCambioForm
from .models import TasaCambio

# Quién administra la tasa de cambio (debe coincidir con
# core.views.ROLES_CONFIGURACION / ingresos.views.ROLES_CONFIGURACION).
ROLES_CONFIGURACION = ("administrador",)


class TasaCambioListView(RolRequeridoMixin, ListView):
    """Historial de tasas cargadas, más recientes primero."""

    roles_permitidos = ROLES_CONFIGURACION
    model = TasaCambio
    template_name = "cambio/tasa_lista.html"
    context_object_name = "tasas"
    paginate_by = 30


class TasaCambioCreateView(RolRequeridoMixin, CreateView):
    roles_permitidos = ROLES_CONFIGURACION
    model = TasaCambio
    form_class = TasaCambioForm
    template_name = "cambio/tasa_form.html"
    success_url = reverse_lazy("cambio:tasa_lista")

    def form_valid(self, form):
        form.instance.cargada_por = self.request.user
        respuesta = super().form_valid(form)
        registrar(
            self.request, RegistroAuditoria.Accion.CARGAR_TASA,
            modelo="TasaCambio", objeto_id=self.object.pk, descripcion=str(self.object),
        )
        messages.success(self.request, f"Tasa «{self.object}» cargada.")
        return respuesta


class TasaCambioUpdateView(RolRequeridoMixin, UpdateView):
    """Editar el `valor` de una tasa ya cargada. Si tiene aportes en
    «registrado»/«observado», `TasaCambio.save()` los recalcula en cascada
    (D-02 revisado); los «verificado»/«anulado» quedan intactos (D-09)."""

    roles_permitidos = ROLES_CONFIGURACION
    model = TasaCambio
    form_class = TasaCambioForm
    template_name = "cambio/tasa_form.html"
    success_url = reverse_lazy("cambio:tasa_lista")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tiene_transacciones"] = self.object.tiene_transacciones()
        return ctx

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        registrar(
            self.request, RegistroAuditoria.Accion.EDITAR_TASA,
            modelo="TasaCambio", objeto_id=self.object.pk, descripcion=str(self.object),
        )
        messages.success(
            self.request,
            f"Tasa «{self.object}» actualizada. Los aportes registrados u observados que la usan "
            "quedaron recalculados con el nuevo valor.",
        )
        return respuesta
