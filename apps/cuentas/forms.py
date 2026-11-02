from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.filtros import NoOfensivo

from . import servicios
from .models import Usuario, normalizar_email

# Textos exactos de las extensiones de CU-01.
MENSAJE_CONDICIONES = "Debe aceptar las condiciones de uso y la política de datos"
MENSAJE_CLAVE_CORTA = "La contraseña debe tener al menos 10 caracteres"
MENSAJE_CLAVES_DISTINTAS = "Las contraseñas no coinciden"
MENSAJE_NOMBRE_OFENSIVO = "Nombre ofensivo"
MENSAJE_NOMBRE_USADO = "Nombre ya usado"
MENSAJE_CORREO_USADO = "El correo electrónico ingresado ya se encuentra registrado"
MENSAJE_CORREO_SUSPENDIDO = "Correo con suspensión permanente"
MENSAJE_LOGIN_INVALIDO = "Correo o contraseña incorrectos"


class RegistroForm(forms.Form):
    """Registro de un visitante. Crea la cuenta como pendiente."""

    nombre_usuario = forms.CharField(
        label="Nombre de usuario",
        max_length=150,
        validators=[NoOfensivo(MENSAJE_NOMBRE_OFENSIVO)],
    )
    email = forms.EmailField(label="Correo electrónico")
    password1 = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Confirmar contraseña",
        strip=False,
        widget=forms.PasswordInput,
    )
    acepta_condiciones = forms.BooleanField(
        label="Acepto las condiciones de uso y la política de datos",
        error_messages={"required": MENSAJE_CONDICIONES},
    )

    def clean_nombre_usuario(self):
        nombre = self.cleaned_data["nombre_usuario"]
        if Usuario.objects.filter(nombre_usuario__iexact=nombre).exists():
            raise ValidationError(MENSAJE_NOMBRE_USADO, code="nombre_usado")
        return nombre

    def clean_email(self):
        email = normalizar_email(self.cleaned_data["email"])
        if Usuario.objects.filter(email__iexact=email).exists():
            raise ValidationError(MENSAJE_CORREO_USADO, code="correo_usado")
        if servicios.correo_con_suspension_permanente(email):
            raise ValidationError(MENSAJE_CORREO_SUSPENDIDO, code="correo_suspendido")
        return email

    def clean_password1(self):
        clave = self.cleaned_data["password1"]
        usuario = Usuario(email=self.cleaned_data.get("email", ""))
        try:
            validate_password(clave, usuario)
        except ValidationError as error:
            mensajes = []
            for detalle in error.error_list:
                if detalle.code == "password_too_short":
                    mensajes.append(MENSAJE_CLAVE_CORTA)
                else:
                    mensajes.extend(detalle.messages)
            raise ValidationError(mensajes) from error
        return clave

    def clean(self):
        datos = super().clean()
        clave1, clave2 = datos.get("password1"), datos.get("password2")
        if clave1 and clave2 and clave1 != clave2:
            self.add_error("password2", MENSAJE_CLAVES_DISTINTAS)
        return datos

    def save(self):
        datos = self.cleaned_data
        return Usuario.objects.create_user(
            datos["email"],
            datos["nombre_usuario"],
            datos["password1"],
            acepto_condiciones_at=timezone.now(),
        )


class ReenviarConfirmacionForm(forms.Form):
    email = forms.EmailField(label="Correo electrónico")

    def clean_email(self):
        return normalizar_email(self.cleaned_data["email"])


class InicioSesionForm(AuthenticationForm):
    """Inicio de sesión con el correo (CU-02).

    El campo se sigue llamando "username" porque así lo espera Django, pero ahí va el correo.
    """

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": MENSAJE_LOGIN_INVALIDO,
    }
