from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from . import servicios
from .models import Sancion, Usuario

CAMPOS_ALTA = (
    "email",
    "nombre_usuario",
    "password1",
    "password2",
    "rol",
    "estado_cuenta",
)
CAMPOS_CUENTA = (
    "rol",
    "es_organizacion",
    "es_zoonosis",
    "estado_cuenta",
    "is_active",
    "acepto_condiciones_at",
)
CAMPOS_SISTEMA = (
    "last_login",
    "date_joined",
    "fecha_registro",
    "email_hash",
)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = ("email", "nombre_usuario", "rol", "estado_cuenta", "is_staff")
    list_filter = ("rol", "estado_cuenta", "es_organizacion", "is_staff")
    search_fields = ("email", "nombre_usuario")
    ordering = ("email",)
    # is_active no se edita a mano: se deriva de estado_cuenta al guardar.
    readonly_fields = ("is_active", "email_hash", "fecha_registro")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("nombre_usuario", "first_name", "last_name")}),
        ("Cuenta", {"fields": CAMPOS_CUENTA}),
        ("Permisos", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Datos del sistema", {"fields": CAMPOS_SISTEMA}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": CAMPOS_ALTA}),)


class SancionAltaForm(forms.ModelForm):
    """Alta desde el panel: la duración y el resto de los datos los fija la regla de sanciones."""

    autor = None  # quien aplica la sanción; lo completa SancionAdmin.get_form

    class Meta:
        model = Sancion
        fields = ("usuario", "tipo", "motivo")

    def clean(self):
        datos = super().clean()
        usuario = datos.get("usuario")
        if usuario is not None and "motivo" in datos:
            try:
                servicios.verificar_sancion(usuario, datos["motivo"], self.autor)
            except servicios.SancionNoPermitida as error:
                raise ValidationError(str(error)) from error
        return datos


@admin.register(Sancion)
class SancionAdmin(ModelAdmin):
    form = SancionAltaForm
    list_display = ("usuario", "tipo", "inicio", "fin", "vigente", "aplicada_por")
    list_filter = ("tipo",)
    search_fields = ("usuario__email", "usuario__nombre_usuario")
    autocomplete_fields = ("usuario",)
    actions = ["levantar"]

    def get_fields(self, request, obj=None):
        if obj is None:
            return ("usuario", "tipo", "motivo")
        return (
            "usuario",
            "tipo",
            "motivo",
            "inicio",
            "fin",
            "aplicada_por",
            "revocada_en",
            "revocada_por",
            "email_hash",
        )

    def get_form(self, request, obj=None, **kwargs):
        formulario = super().get_form(request, obj, **kwargs)
        formulario.autor = request.user
        return formulario

    # Las sanciones quedan como registro: no se editan ni se borran, solo se levantan.
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(boolean=True, description="Vigente")
    def vigente(self, obj):
        return Sancion.objects.vigentes().filter(pk=obj.pk).exists()

    def save_model(self, request, obj, form, change):
        creada = servicios.sancionar(obj.usuario, obj.tipo, obj.motivo, request.user)
        # El panel sigue trabajando con "obj": se lo completa con lo que guardó la regla.
        obj.__dict__.update(creada.__dict__)

    @admin.action(description="Levantar las sanciones seleccionadas")
    def levantar(self, request, queryset):
        levantadas = 0
        for sancion in queryset:
            try:
                servicios.levantar_sancion(sancion, request.user)
            except servicios.SancionNoPermitida as error:
                self.message_user(request, f"{sancion}: {error}", messages.WARNING)
            else:
                levantadas += 1
        if levantadas:
            self.message_user(request, f"Sanciones levantadas: {levantadas}.", messages.SUCCESS)
