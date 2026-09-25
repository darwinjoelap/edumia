from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError

from academico.models import Grado, Seccion
from gastos.models import Fondo

from .models import Institucion, PerfilUsuario, PeriodoEscolar


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


# --- Usuarios (Fase 8) -------------------------------------------------------
# Un User de Django + su PerfilUsuario se crean/editan juntos, así que estos
# dos formularios no son ModelForm (abarcan dos modelos): guardan ellos mismos
# en save(), dentro de una transacción que arma la vista.


class UsuarioCreateForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label="Usuario",
        help_text="Con qué inicia sesión. Sugerencia: su cédula sin puntos ni guiones (ej. V12345678).",
    )
    first_name = forms.CharField(max_length=150, label="Nombre")
    last_name = forms.CharField(max_length=150, label="Apellido")
    email = forms.EmailField(required=False, label="Correo (opcional)")
    telefono = forms.CharField(max_length=20, required=False, label="Teléfono (opcional)")
    rol = forms.ChoiceField(choices=PerfilUsuario.Rol.choices, label="Rol")
    fondo = forms.ModelChoiceField(
        queryset=Fondo.objects.filter(activo=True), required=False, label="Fondo a cargo",
        help_text="Solo para el rol «Responsable de fondo».",
    )
    password1 = forms.CharField(widget=forms.PasswordInput, label="Contraseña temporal")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Repetir contraseña")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, field in self.fields.items():
            css = "form-select" if nombre in ("rol", "fondo") else "form-control"
            field.widget.attrs.setdefault("class", css)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise ValidationError("Ya existe un usuario con ese nombre de usuario.")
        return username

    def clean(self):
        cleaned = super().clean()
        rol = cleaned.get("rol")
        fondo = cleaned.get("fondo")
        if rol == PerfilUsuario.Rol.RESPONSABLE_FONDO and not fondo:
            self.add_error("fondo", "El rol «Responsable de fondo» exige elegir un fondo.")
        elif rol != PerfilUsuario.Rol.RESPONSABLE_FONDO:
            cleaned["fondo"] = None

        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Las dos contraseñas no coinciden.")
        elif password1:
            try:
                password_validation.validate_password(password1)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned

    def save(self):
        User = get_user_model()
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            email=self.cleaned_data.get("email") or "",
            password=self.cleaned_data["password1"],
        )
        perfil = PerfilUsuario.objects.create(
            user=user,
            rol=self.cleaned_data["rol"],
            fondo=self.cleaned_data.get("fondo"),
            telefono=self.cleaned_data.get("telefono") or "",
            debe_cambiar_clave=True,
        )
        return user, perfil


class UsuarioUpdateForm(forms.Form):
    """Edita datos y rol de un usuario existente. La contraseña se cambia
    aparte, en RestablecerClaveForm (acción explícita, no un campo más)."""

    first_name = forms.CharField(max_length=150, label="Nombre")
    last_name = forms.CharField(max_length=150, label="Apellido")
    email = forms.EmailField(required=False, label="Correo (opcional)")
    telefono = forms.CharField(max_length=20, required=False, label="Teléfono (opcional)")
    rol = forms.ChoiceField(choices=PerfilUsuario.Rol.choices, label="Rol")
    fondo = forms.ModelChoiceField(
        queryset=Fondo.objects.filter(activo=True), required=False, label="Fondo a cargo",
        help_text="Solo para el rol «Responsable de fondo».",
    )
    is_active = forms.BooleanField(required=False, label="Usuario activo (puede iniciar sesión)")

    def __init__(self, *args, usuario=None, **kwargs):
        self.usuario = usuario
        initial = kwargs.pop("initial", {}) or {}
        if usuario is not None and not initial:
            perfil = getattr(usuario, "perfilusuario", None)
            initial = {
                "first_name": usuario.first_name,
                "last_name": usuario.last_name,
                "email": usuario.email,
                "telefono": perfil.telefono if perfil else "",
                "rol": perfil.rol if perfil else "",
                "fondo": perfil.fondo_id if perfil else None,
                "is_active": usuario.is_active,
            }
        super().__init__(*args, initial=initial, **kwargs)
        for nombre, field in self.fields.items():
            if nombre == "is_active":
                field.widget.attrs.setdefault("class", "form-check-input")
                continue
            css = "form-select" if nombre in ("rol", "fondo") else "form-control"
            field.widget.attrs.setdefault("class", css)

    def clean(self):
        cleaned = super().clean()
        rol = cleaned.get("rol")
        fondo = cleaned.get("fondo")
        if rol == PerfilUsuario.Rol.RESPONSABLE_FONDO and not fondo:
            self.add_error("fondo", "El rol «Responsable de fondo» exige elegir un fondo.")
        elif rol != PerfilUsuario.Rol.RESPONSABLE_FONDO:
            cleaned["fondo"] = None
        return cleaned

    def save(self):
        user = self.usuario
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data.get("email") or ""
        user.is_active = self.cleaned_data["is_active"]
        user.save(update_fields=["first_name", "last_name", "email", "is_active"])

        perfil, _ = PerfilUsuario.objects.get_or_create(user=user, defaults={"rol": self.cleaned_data["rol"]})
        perfil.rol = self.cleaned_data["rol"]
        perfil.fondo = self.cleaned_data.get("fondo")
        perfil.telefono = self.cleaned_data.get("telefono") or ""
        perfil.full_clean()
        perfil.save()
        return user, perfil


class RestablecerClaveForm(forms.Form):
    password1 = forms.CharField(widget=forms.PasswordInput, label="Contraseña temporal nueva")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Repetir contraseña")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Las dos contraseñas no coinciden.")
        elif password1:
            try:
                password_validation.validate_password(password1)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned

    def save(self, usuario):
        usuario.set_password(self.cleaned_data["password1"])
        usuario.save(update_fields=["password"])
        perfil = getattr(usuario, "perfilusuario", None)
        if perfil:
            perfil.debe_cambiar_clave = True
            perfil.save(update_fields=["debe_cambiar_clave"])
        return usuario
