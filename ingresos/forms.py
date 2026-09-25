from django import forms
from django.utils import timezone

from academico.models import Grado, Inscripcion, Representante
from cambio.models import TasaCambio
from core.models import PeriodoEscolar
from gastos.models import Fondo

from .models import Aporte, Banco, ConceptoIngreso, FormaPago, MontoConcepto


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


class MontoConceptoForm(forms.ModelForm):
    """Monto esperado de un concepto para un grado y período (D-07): se usa
    para la validación de desviación en `Aporte.clean()` — sin esta fila, se
    cae a `concepto.monto_sugerido` (o no se valida desviación)."""

    class Meta:
        model = MontoConcepto
        fields = ["concepto", "grado", "periodo", "monto", "moneda"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["concepto"].queryset = ConceptoIngreso.objects.filter(activo=True).order_by("nombre")
        self.fields["grado"].queryset = Grado.objects.order_by("orden")
        self.fields["periodo"].queryset = PeriodoEscolar.objects.order_by("-fecha_inicio")
        for nombre, field in self.fields.items():
            es_select = nombre in ("concepto", "grado", "periodo", "moneda")
            field.widget.attrs.setdefault("class", "form-select" if es_select else "form-control")


class AporteLoteEncabezadoForm(forms.Form):
    """Datos comunes a todos los aportes de un lote (registro por sección,
    para el docente): mismo concepto, forma de pago, fecha y moneda para
    todos los estudiantes que pagaron ese día. Lo que varía por estudiante
    (monto, referencia, etc.) va en `AporteLoteFilaForm`."""

    concepto = forms.ModelChoiceField(
        queryset=ConceptoIngreso.objects.none(), required=False, label="Concepto",
    )
    concepto_libre = forms.CharField(
        max_length=150, required=False, label="Concepto (no está en la lista)",
    )
    mes_cubierto = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}), label="Período que cubre",
    )
    moneda = forms.ChoiceField(choices=Aporte.Moneda.choices, label="Moneda")
    tasa = forms.ModelChoiceField(queryset=TasaCambio.objects.none(), label="Tasa")
    forma_pago = forms.ModelChoiceField(queryset=FormaPago.objects.none(), label="Forma de pago")
    fecha_pago = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), label="Fecha de pago")
    banco_destino = forms.ModelChoiceField(
        queryset=Banco.objects.none(), required=False, label="Banco destino",
    )
    entregado_por_nombre = forms.CharField(
        max_length=150, required=False, label="Entregado por",
        help_text="Quién le entrega el dinero recolectado al fondo (normalmente el docente).",
    )

    def __init__(self, *args, **kwargs):
        entregado_por_inicial = kwargs.pop("entregado_por_inicial", "")
        super().__init__(*args, **kwargs)
        self.fields["concepto"].queryset = ConceptoIngreso.objects.filter(activo=True).order_by("nombre")
        self.fields["forma_pago"].queryset = FormaPago.objects.filter(activo=True).order_by("nombre")
        self.fields["banco_destino"].queryset = Banco.objects.filter(activo=True).order_by("nombre")

        tasas_recientes = TasaCambio.objects.order_by("-fecha", "-creada_en")[:30]
        self.fields["tasa"].queryset = TasaCambio.objects.filter(pk__in=[t.pk for t in tasas_recientes])
        if tasas_recientes and not self.is_bound:
            self.fields["tasa"].initial = tasas_recientes[0].pk

        if not self.is_bound:
            self.fields["fecha_pago"].initial = timezone.localdate()
            self.fields["entregado_por_nombre"].initial = entregado_por_inicial

        for nombre, field in self.fields.items():
            es_select = nombre in ("concepto", "moneda", "tasa", "forma_pago", "banco_destino")
            field.widget.attrs.setdefault("class", "form-select" if es_select else "form-control")

    def clean(self):
        cleaned = super().clean()
        concepto = cleaned.get("concepto")
        concepto_libre = cleaned.get("concepto_libre")
        if concepto and concepto_libre:
            self.add_error("concepto_libre", "Elige un concepto del catálogo o escribe uno libre, no los dos.")
        elif not concepto and not concepto_libre:
            self.add_error("concepto", "Elige un concepto del catálogo o escribe uno para este lote.")
        return cleaned


class AporteLoteFilaForm(forms.Form):
    """Una fila del lote: un estudiante que sí pagó (fila vacía = no pagó,
    se ignora sin error, igual que en la alta rápida de estudiantes)."""

    inscripcion_id = forms.IntegerField(widget=forms.HiddenInput)
    monto = forms.DecimalField(max_digits=18, decimal_places=4, required=False, label="Monto")
    referencia = forms.CharField(max_length=40, required=False, label="Referencia")
    cedula_titular = forms.CharField(max_length=20, required=False, label="Cédula")
    telefono_emisor = forms.CharField(max_length=11, required=False, label="Teléfono")
    banco_origen = forms.ModelChoiceField(
        queryset=Banco.objects.filter(activo=True).order_by("nombre"), required=False, label="Banco origen",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, field in self.fields.items():
            if nombre == "inscripcion_id":
                continue
            es_select = nombre == "banco_origen"
            field.widget.attrs.setdefault("class", "form-select form-select-sm" if es_select else "form-control form-control-sm")

    def fila_vacia(self):
        datos = getattr(self, "cleaned_data", None) or {}
        return not datos.get("monto")


AporteLoteFormSet = forms.formset_factory(AporteLoteFilaForm, extra=0)
