from django import forms

from academico.models import Grado, Seccion
from gastos.models import CategoriaGasto, Fondo, Producto


def _marcar_clases(form, selects=()):
    for nombre, field in form.fields.items():
        es_select = nombre in selects
        field.widget.attrs.setdefault("class", "form-select" if es_select else "form-control")


class _FiltroFechasMixin(forms.Form):
    desde = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    hasta = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))


class FiltroIngresosForm(_FiltroFechasMixin):
    grado = forms.ModelChoiceField(queryset=Grado.objects.all(), required=False, label="Grado")
    seccion = forms.ModelChoiceField(queryset=Seccion.objects.select_related("grado"), required=False, label="Sección")
    solo_verificados = forms.BooleanField(required=False, initial=True, label="Solo aportes verificados")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _marcar_clases(self, selects=("grado", "seccion"))
        self.fields["solo_verificados"].widget.attrs["class"] = "form-check-input"


class FiltroGastosForm(_FiltroFechasMixin):
    fondo = forms.ModelChoiceField(queryset=Fondo.objects.all(), required=False, label="Fondo")
    categoria = forms.ModelChoiceField(queryset=CategoriaGasto.objects.all(), required=False, label="Categoría")
    producto = forms.ModelChoiceField(queryset=Producto.objects.select_related("categoria"), required=False, label="Producto")

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        _marcar_clases(self, selects=("fondo", "categoria", "producto"))
        from .services import fondo_bloqueado_para

        fondo_fijo = fondo_bloqueado_para(usuario) if usuario else None
        if fondo_fijo:
            self.fields["fondo"].queryset = Fondo.objects.filter(pk=fondo_fijo.pk)
            self.fields["fondo"].initial = fondo_fijo
            self.fields["fondo"].disabled = True


class FiltroBalanceForm(_FiltroFechasMixin):
    fondo = forms.ModelChoiceField(queryset=Fondo.objects.all(), required=False, label="Fondo")

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        _marcar_clases(self, selects=("fondo",))
        from .services import fondo_bloqueado_para

        fondo_fijo = fondo_bloqueado_para(usuario) if usuario else None
        if fondo_fijo:
            self.fields["fondo"].queryset = Fondo.objects.filter(pk=fondo_fijo.pk)
            self.fields["fondo"].initial = fondo_fijo
            self.fields["fondo"].disabled = True


class BuscarEstudianteForm(forms.Form):
    q = forms.CharField(required=False, label="Buscar", widget=forms.TextInput(
        attrs={"class": "form-control", "placeholder": "Nombre, apellido o cédula escolar"},
    ))
