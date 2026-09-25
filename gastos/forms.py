from django import forms

from cambio.models import TasaCambio

from .models import CategoriaGasto, DetalleGasto, Fondo, Gasto, Producto, Proveedor, UnidadMedida


def _marcar_clases(form, selects=()):
    for nombre, field in form.fields.items():
        if isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs.setdefault("class", "form-check-input")
            continue
        es_select = nombre in selects
        field.widget.attrs.setdefault("class", "form-select" if es_select else "form-control")


class GastoForm(forms.ModelForm):
    """Cabecera del gasto. Los renglones se capturan aparte (`DetalleGastoFormSet`);
    `monto`/`monto_ves`/`monto_usd` los calcula `Gasto.recalcular()` a partir de
    ellos, así que no aparecen aquí."""

    class Meta:
        model = Gasto
        fields = [
            "fecha", "fondo", "proveedor", "tipo_documento", "numero_documento",
            "moneda", "tasa", "observacion",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "observacion": forms.Textarea(attrs={"rows": 2}),
            "numero_documento": forms.TextInput(attrs={"placeholder": "Ej: 00012345"}),
        }
        labels = {"numero_documento": "Número de documento"}
        help_texts = {
            "observacion": "Obligatoria si el tipo de documento es «Sin soporte».",
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fondo"].queryset = Fondo.objects.filter(activo=True).order_by("nombre")
        self.fields["proveedor"].queryset = Proveedor.objects.filter(activo=True).order_by("nombre")
        self.fields["proveedor"].required = False
        self.fields["numero_documento"].required = False

        tasas_recientes = TasaCambio.objects.order_by("-fecha", "-creada_en")[:30]
        self.fields["tasa"].queryset = TasaCambio.objects.filter(pk__in=[t.pk for t in tasas_recientes])
        tasa_actual = tasas_recientes[0] if tasas_recientes else None
        if tasa_actual and not self.instance.pk:
            self.fields["tasa"].initial = tasa_actual.pk

        # Validación 5 (MODELOS_gastos.md): un responsable de fondo solo
        # puede registrar en su propio fondo; se restringe aquí acotando el
        # queryset, así que aunque manipulen el POST, el ModelChoiceField
        # rechaza cualquier otro fondo como "opción no válida".
        if usuario is not None and not usuario.is_superuser:
            perfil = getattr(usuario, "perfilusuario", None)
            if perfil and perfil.rol == "responsable_fondo" and perfil.fondo_id:
                self.fields["fondo"].queryset = Fondo.objects.filter(pk=perfil.fondo_id)
                if not self.instance.pk:
                    self.fields["fondo"].initial = perfil.fondo_id

        _marcar_clases(self, selects=("fondo", "proveedor", "tipo_documento", "moneda", "tasa"))


class DetalleGastoForm(forms.ModelForm):
    """Un renglón. Tanto `producto` como `descripcion` quedan opcionales a
    nivel de formulario porque la exigencia real ("uno de los dos") vive en
    `DetalleGasto.clean()`; así el mensaje sale del modelo, no duplicado aquí."""

    class Meta:
        model = DetalleGasto
        fields = ["producto", "descripcion", "cantidad", "unidad", "precio_unitario"]
        widgets = {
            "descripcion": forms.TextInput(attrs={"placeholder": "Si el producto no está en el catálogo"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto"].queryset = Producto.objects.filter(activo=True).order_by("nombre")
        self.fields["producto"].required = False
        self.fields["descripcion"].required = False
        self.fields["unidad"].queryset = UnidadMedida.objects.order_by("nombre")
        for nombre, field in self.fields.items():
            es_select = nombre in ("producto", "unidad")
            field.widget.attrs.setdefault(
                "class", "form-select form-select-sm" if es_select else "form-control form-control-sm",
            )


DetalleGastoFormSet = forms.inlineformset_factory(
    Gasto, DetalleGasto, form=DetalleGastoForm, extra=1, can_delete=True,
    min_num=1, validate_min=True,
)


class CategoriaGastoForm(forms.ModelForm):
    class Meta:
        model = CategoriaGasto
        fields = ["nombre", "fondo", "activo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fondo"].queryset = Fondo.objects.filter(activo=True).order_by("nombre")
        self.fields["fondo"].required = False
        _marcar_clases(self, selects=("fondo",))


class UnidadMedidaForm(forms.ModelForm):
    class Meta:
        model = UnidadMedida
        fields = ["nombre", "abreviatura"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _marcar_clases(self)


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ["nombre", "categoria", "unidad_default", "activo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = CategoriaGasto.objects.filter(activo=True).order_by("nombre")
        self.fields["unidad_default"].queryset = UnidadMedida.objects.order_by("nombre")
        _marcar_clases(self, selects=("categoria", "unidad_default"))


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ["nombre", "rif", "telefono", "direccion", "activo"]
        widgets = {"direccion": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rif"].required = False
        _marcar_clases(self)


class FondoForm(forms.ModelForm):
    """`es_general` no se edita aquí a propósito: ya hay exactamente un Fondo
    General (creado por `seed_datos_iniciales`, protegido por la restricción
    `un_solo_fondo_general`) y no tiene sentido cambiar cuál lo es desde esta
    pantalla — eso, si algún día hiciera falta, se hace desde `/admin/`."""

    class Meta:
        model = Fondo
        fields = ["nombre", "descripcion", "saldo_inicial_ves", "saldo_inicial_usd", "activo"]
        widgets = {"descripcion": forms.TextInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _marcar_clases(self)
