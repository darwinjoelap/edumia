from django import forms

from academico.models import Inscripcion, Representante
from cambio.models import TasaCambio
from core.models import PeriodoEscolar

from gastos.models import Fondo

from .models import Aporte, Banco, ConceptoIngreso, FormaPago


class AporteForm(forms.ModelForm):
    """Registro individual de un aporte. El registro en lote por sección
    (para el docente) usa otra pantalla, no este formulario.

    Campos que NO aparecen aquí porque los pone la vista o el propio modelo:
    `periodo`/`fondo` (se autocompletan en `Aporte.save()`),
    `tasa_aplicada`/`monto_ves`/`monto_usd` (calculados),
    `estado`/`registrado_por`/`fecha_registro` (los fija la vista al crear).
    """

    class Meta:
        model = Aporte
        fields = [
            "concepto", "concepto_libre", "mes_cubierto",
            "monto", "moneda", "tasa",
            "forma_pago", "fecha_pago",
            "banco_destino", "banco_origen", "referencia",
            "telefono_emisor", "cedula_titular", "nombre_titular", "nota_pago",
            "entregado_por", "entregado_por_nombre",
            "inscripcion",
            "desviacion_confirmada",
        ]
        widgets = {
            "fecha_pago": forms.DateInput(attrs={"type": "date"}),
            "mes_cubierto": forms.DateInput(attrs={"type": "date"}),
            "nota_pago": forms.Textarea(attrs={"rows": 2}),
            "concepto_libre": forms.TextInput(attrs={"placeholder": "Ej: Rifa del día del niño"}),
        }
        labels = {
            "concepto_libre": "Concepto (no está en la lista)",
            "mes_cubierto": "Período que cubre",
            "desviacion_confirmada": "Confirmo el monto aunque se desvíe del esperado",
            "inscripcion": "Estudiante",
        }
        help_texts = {
            "concepto": "Elige uno de la lista, o escribe uno nuevo abajo si es un ingreso no planificado.",
            "concepto_libre": "Solo si el concepto no está en la lista de arriba (no queda guardado para "
            "la próxima vez; el ingreso entra al Fondo General).",
            "inscripcion": "Solo si este ingreso corresponde a un estudiante en particular.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        periodo_activo = PeriodoEscolar.objects.filter(activo=True).first()
        inscripciones = Inscripcion.objects.filter(estado=Inscripcion.Estado.ACTIVO).select_related(
            "estudiante", "seccion__grado",
        )
        if periodo_activo:
            inscripciones = inscripciones.filter(periodo=periodo_activo)
        self.fields["inscripcion"].queryset = inscripciones.order_by(
            "seccion__grado__orden", "seccion__nombre", "estudiante__apellidos",
        )
        self.fields["inscripcion"].label_from_instance = (
            lambda obj: f"{obj.estudiante} — {obj.seccion}"
        )
        self.fields["inscripcion"].required = False

        self.fields["concepto"].queryset = ConceptoIngreso.objects.filter(activo=True).order_by("nombre")
        self.fields["concepto"].required = False
        self.fields["concepto_libre"].required = False
        self.fields["forma_pago"].queryset = FormaPago.objects.filter(activo=True).order_by("nombre")
        self.fields["banco_destino"].queryset = Banco.objects.filter(activo=True).order_by("nombre")
        self.fields["banco_origen"].queryset = Banco.objects.filter(activo=True).order_by("nombre")
        self.fields["banco_destino"].required = False
        self.fields["banco_origen"].required = False

        tasas_recientes = TasaCambio.objects.order_by("-fecha", "-creada_en")[:30]
        self.fields["tasa"].queryset = TasaCambio.objects.filter(
            pk__in=[t.pk for t in tasas_recientes],
        )
        tasa_actual = tasas_recientes[0] if tasas_recientes else None
        if tasa_actual and not self.instance.pk:
            self.fields["tasa"].initial = tasa_actual.pk

        self.fields["entregado_por"].queryset = Representante.objects.filter(activo=True).order_by(
            "apellidos", "nombres",
        )
        self.fields["entregado_por"].required = False
        self.fields["entregado_por_nombre"].required = False
        self.fields["desviacion_confirmada"].required = False

        for nombre, field in self.fields.items():
            if nombre == "desviacion_confirmada":
                field.widget.attrs.setdefault("class", "form-check-input")
                continue
            es_select = nombre in (
                "inscripcion", "concepto", "moneda", "tasa", "forma_pago",
                "banco_destino", "banco_origen", "entregado_por",
            )
            field.widget.attrs.setdefault("class", "form-select" if es_select else "form-control")

    def clean_mes_cubierto(self):
        valor = self.cleaned_data.get("mes_cubierto")
        if valor:
            valor = valor.replace(day=1)
        return valor

    def _post_clean(self):
        # Se resuelve periodo/fondo ANTES de clean_fields()/clean() del
        # modelo (que ModelForm llama por su cuenta): si no, la validación
        # de "fecha dentro del período" nunca ve un período asignado.
        self.instance._autocompletar_periodo_y_fondo()
        super()._post_clean()


class ConceptoIngresoForm(forms.ModelForm):
    class Meta:
        model = ConceptoIngreso
        fields = ["nombre", "periodicidad", "monto_sugerido", "moneda_sugerida", "fondo", "activo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fondo"].queryset = Fondo.objects.filter(activo=True).order_by("nombre")
        self.fields["fondo"].required = False
        self.fields["monto_sugerido"].required = False
        self.fields["moneda_sugerida"].required = False
        for nombre, field in self.fields.items():
            if nombre == "activo":
                field.widget.attrs.setdefault("class", "form-check-input")
                continue
            es_select = nombre in ("periodicidad", "moneda_sugerida", "fondo")
            field.widget.attrs.setdefault("class", "form-select" if es_select else "form-control")


class FormaPagoForm(forms.ModelForm):
    class Meta:
        model = FormaPago
        fields = [
            "nombre", "moneda_fija", "requiere_banco_destino", "requiere_banco_origen",
            "requiere_referencia", "requiere_telefono", "requiere_cedula", "activo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["moneda_fija"].required = False
        for nombre, field in self.fields.items():
            if nombre in ("requiere_banco_destino", "requiere_banco_origen", "requiere_referencia",
                          "requiere_telefono", "requiere_cedula", "activo"):
                field.widget.attrs.setdefault("class", "form-check-input")
                continue
            es_select = nombre == "moneda_fija"
            field.widget.attrs.setdefault("class", "form-select" if es_select else "form-control")
