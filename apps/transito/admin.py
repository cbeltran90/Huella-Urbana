from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.template.response import TemplateResponse
from django.urls import reverse
from unfold.admin import ModelAdmin

from apps.cuentas.permisos_admin import es_moderador_o_administrador

from . import servicios
from .models import PerfilTransito


@admin.register(PerfilTransito)
class PerfilTransitoAdmin(ModelAdmin):
    """Perfiles de hogar de tránsito: los ven el moderador y el administrador.

    Son solo de consulta: los completa cada persona. Lo único que se hace desde
    acá es retirar el rol de hogar de tránsito.
    """

    list_display = (
        "usuario",
        "especies_aceptadas",
        "tamano_maximo",
        "cupo_declarado",
        "disponibilidad",
        "activo",
    )
    list_filter = ("activo", "disponibilidad")
    list_select_related = ("usuario",)
    search_fields = ("usuario__email", "usuario__nombre_usuario")
    ordering = ("usuario__email",)
    actions = ["retirar_rol"]

    def has_module_permission(self, request):
        return es_moderador_o_administrador(request)

    def has_view_permission(self, request, obj=None):
        return es_moderador_o_administrador(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_retirar_permission(self, request):
        return es_moderador_o_administrador(request)

    @admin.action(description="Retirar el rol de hogar de tránsito", permissions=["retirar"])
    def retirar_rol(self, request, queryset):
        # Primero se pide confirmar (CU-07, paso 5); cancelar no cambia nada (5A).
        if request.POST.get("confirmar") != "1":
            contexto = {
                **self.admin_site.each_context(request),
                "title": "Retirar el rol de hogar de tránsito",
                "opts": self.model._meta,
                "queryset": queryset,
                "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
                "volver": reverse("admin:transito_perfiltransito_changelist"),
            }
            return TemplateResponse(request, "transito/admin_retirar_rol.html", contexto)

        retirados = 0
        for perfil in queryset.select_related("usuario"):
            try:
                servicios.retirar_rol_transito(perfil.usuario, request.user)
            except (servicios.RetiroNoPermitido, servicios.SinPerfilActivo) as error:
                self.message_user(request, f"{perfil.usuario}: {error}", messages.WARNING)
            else:
                retirados += 1
        if retirados:
            self.message_user(
                request, f"Roles de hogar de tránsito retirados: {retirados}.", messages.SUCCESS
            )
