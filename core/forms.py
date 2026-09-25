from django import forms
from django.contrib.auth import get_user_model

from academico.models import Grado, Seccion

from .models import Institucion, PeriodoEscolar


class InstitucionForm(forms.ModelForm):
    class Meta:
        model = Institucion
        fields = ["nombre", "rif", "direccion", "telefono", "email", "permitir_autoaprobacion"]
        widgets = {
            "direccion": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {"permitir_autoaprobacion": "Permitir que un administrador apruebe sus propios gastos"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, field in self.fields.items():
            if nombre == "permitir_autoaprobacion":
                field.widget.attrs.setdefault("class", "form-check-input")
                continue
            field.widget.attrs.setdefault("class", "form-control")


class GradoForm(forms.ModelForm):
    class Meta:
        model = Grado
        fields = ["nombre", "nivel", "orden"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, field in self.fields.items():
            css = "form-select" if nombre == "nivel" else "form-control"
            field.widget.attrs.setdefault("class", css)


class PeriodoEscolarForm(forms.ModelForm):
    class Meta:
        model = PeriodoEscolar
        fields = ["nombre", "fecha_inicio", "fecha_fin"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class SeccionForm(forms.ModelForm):
    """Una sección pertenece a un grado y a un período (D-20/Fase 1): así
    '1er grado' puede tener las secciones A, B, C, cada una con su propio
    docente responsable."""

    class Meta:
        model = Seccion
        fields = ["grado", "periodo", "nombre", "docente_responsable", "activa"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grado"].queryset = Grado.objects.order_by("orden")
        self.fields["periodo"].queryset = PeriodoEscolar.objects.order_by("-fecha_inicio")
        self.fields["docente_responsable"].queryset = (
            get_user_model().objects.filter(perfilusuario__rol="docente").order_by("last_name", "first_name")
        )
        self.fields["docente_responsable"].required = False
        for nombre, field in self.fields.items():
            if nombre == "activa":
                field.widget.attrs.setdefault("class", "form-check-input")
                continue
            css = "form-select" if nombre in ("grado", "periodo", "docente_responsable") else "form-control"
            field.widget.attrs.setdefault("class", css)
