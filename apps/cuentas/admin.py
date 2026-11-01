from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import Usuario

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
