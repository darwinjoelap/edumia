from django import forms

from academico.models import Grado

from .models import Institucion, PeriodoEscolar


class InstitucionForm(forms.ModelForm):
    class Meta:
        model = Institucion
        fields = ["nombre", "rif", "codigo_dea", "direccion", "telefono", "email"]
        widgets = {
            "direccion": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
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
