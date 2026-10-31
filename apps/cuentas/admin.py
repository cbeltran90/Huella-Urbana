from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin, ModelAdmin):
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    # Evitamos que el UserAdmin busque 'username' (que eliminamos)
    ordering = ("email",)

    # Columnas que se ven en el listado del admin
    list_display = ("email", "nombre_usuario", "rol", "estado_cuenta", "is_staff")
    search_fields = ("email", "nombre_usuario")

    # Organización del formulario de edición de usuario
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Información personal", {"fields": ("nombre_usuario", "first_name", "last_name")}),
        (
            "Permisos",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Fechas importantes", {"fields": ("last_login", "date_joined")}),
        (
            "Datos del sistema (DER)",
            {
                "fields": (
                    "rol",
                    "es_organizacion",
                    "es_zoonosis",
                    "estado_cuenta",
                    "acepto_condiciones_at",
                )
            },
        ),
    )

    # Organización del formulario de creación de usuario
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "nombre_usuario", "password1", "password2"),
            },
        ),
    )
