from django.contrib import admin, messages
from unfold.admin import ModelAdmin

from apps.cuentas.permisos_admin import es_moderador_o_administrador

from . import moderacion
from .models import Publicacion


@admin.register(Publicacion)
class PublicacionAdmin(ModelAdmin):
    """Publicaciones: las ven el moderador y el administrador.

    Son solo de consulta. Lo único que se hace desde acá es eliminarlas (baja lógica).
    """

    list_display = ("id", "tipo", "estado", "autor", "ficha", "fecha")
    list_filter = ("tipo", "estado")
    search_fields = ("descripcion", "autor__nombre_usuario")
    actions = ["eliminar_publicacion"]

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

    def has_eliminar_permission(self, request):
        return es_moderador_o_administrador(request)

    @admin.action(description="Eliminar publicación", permissions=["eliminar"])
    def eliminar_publicacion(self, request, queryset):
        eliminadas = 0
        for publicacion in queryset:
            if moderacion.eliminar_publicacion(publicacion, request.user):
                eliminadas += 1
        if eliminadas:
            self.message_user(request, f"Publicaciones eliminadas: {eliminadas}.", messages.SUCCESS)
        else:
            self.message_user(
                request, "Esas publicaciones ya estaban eliminadas.", messages.WARNING
            )
