from django import forms

from core.models import PeriodoEscolar

from .models import Estudiante, EstudianteRepresentante, Representante

CAMPOS_REQUERIDOS_SI_FILA_NO_VACIA = ("nombres", "apellidos", "fecha_nacimiento", "sexo")
CAMPOS_QUE_INDICAN_FILA_CON_DATOS = ("nombres", "apellidos", "fecha_nacimiento", "cedula_escolar")


class EstudianteRapidoForm(forms.ModelForm):
    """Una fila de la tabla de alta rápida (D-20).

    Todos los campos son opcionales a nivel de Django Form: una fila vacía
    (el usuario no llegó a llenarla) debe poder ignorarse sin error. La
    validación real —qué es obligatorio cuando SÍ hay datos— vive en clean().
    """

    class Meta:
        model = Estudiante
        fields = ["nombres", "apellidos", "fecha_nacimiento", "sexo", "cedula_escolar"]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, field in self.fields.items():
            field.required = False
            css = "form-select form-select-sm" if nombre == "sexo" else "form-control form-control-sm"
            field.widget.attrs.setdefault("class", css)

    def fila_vacia(self):
        datos = getattr(self, "cleaned_data", None) or {}
        return not any(datos.get(campo) for campo in CAMPOS_QUE_INDICAN_FILA_CON_DATOS)

    def clean(self):
        cleaned = super().clean()
        if self.fila_vacia():
            return cleaned
        faltantes = [
            self.fields[campo].label or campo
            for campo in CAMPOS_REQUERIDOS_SI_FILA_NO_VACIA
            if not cleaned.get(campo)
        ]
        if faltantes:
            raise forms.ValidationError(f"Completa estos campos: {', '.join(faltantes)}.")
        return cleaned


class EstudianteRapidoBaseFormSet(forms.BaseFormSet):
    """Evita que dos filas de la misma tabla usen la misma cédula escolar."""

    def clean(self):
        if any(self.errors):
            return
        vistas = set()
        for form in self.forms:
            if form.fila_vacia():
                continue
            cedula = form.cleaned_data.get("cedula_escolar")
            if not cedula:
                continue
            if cedula in vistas:
                form.add_error("cedula_escolar", "Cédula repetida en esta misma tabla.")
            vistas.add(cedula)


def construir_formset_alta_rapida(filas=10):
    return forms.formset_factory(
        EstudianteRapidoForm,
        formset=EstudianteRapidoBaseFormSet,
        extra=filas,
        can_delete=False,
    )


EXTENSIONES_PERMITIDAS = (".xlsx", ".csv")


class ImportarArchivoForm(forms.Form):
    archivo = forms.FileField(
        label="Archivo (.xlsx o .csv)",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".xlsx,.csv"}),
    )

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        nombre = archivo.name.lower()
        if not nombre.endswith(EXTENSIONES_PERMITIDAS):
            raise forms.ValidationError("Solo se aceptan archivos .xlsx o .csv.")
        return archivo


class RepresentanteForm(forms.ModelForm):
    class Meta:
        model = Representante
        fields = ["nombres", "apellidos", "cedula", "telefono", "email", "direccion"]
        widgets = {
            "direccion": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, field in self.fields.items():
            css = "form-control" if nombre != "direccion" else "form-control"
            field.widget.attrs.setdefault("class", css)


class EstudianteEditForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = ["nombres", "apellidos", "fecha_nacimiento", "sexo", "cedula_escolar"]
        widgets = {
            "fecha_nacimiento": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, field in self.fields.items():
            css = "form-select" if nombre == "sexo" else "form-control"
            field.widget.attrs.setdefault("class", css)


class VinculoRepresentanteForm(forms.ModelForm):
    """Usado desde la ficha del representante para agregar un vínculo a un
    estudiante existente. El representante se asigna en la vista, no aquí."""

    class Meta:
        model = EstudianteRepresentante
        fields = ["estudiante", "parentesco", "es_principal"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estudiante"].queryset = self.fields["estudiante"].queryset.order_by(
            "apellidos", "nombres"
        )
        self.fields["estudiante"].widget.attrs.setdefault("class", "form-select")
        self.fields["parentesco"].widget.attrs.setdefault("class", "form-select")


class PromocionForm(forms.Form):
    periodo_destino = forms.ModelChoiceField(
        queryset=PeriodoEscolar.objects.none(),
        label="Período destino (al que se promueve)",
    )

    def __init__(self, *args, periodo_origen=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = PeriodoEscolar.objects.order_by("-fecha_inicio")
        if periodo_origen is not None:
            qs = qs.exclude(pk=periodo_origen.pk)
        self.fields["periodo_destino"].queryset = qs
        self.fields["periodo_destino"].widget.attrs.setdefault("class", "form-select")
