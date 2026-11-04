from constance.admin import Config, ConstanceAdmin
from django.contrib import admin
from unfold.admin import ModelAdmin

from apps.cuentas.permisos_admin import es_administrador

# Constance registra su pantalla con el estilo estándar de Django: se vuelve a registrar
# con el de Unfold y con los permisos atados al rol.
admin.site.unregister([Config])


@admin.register(Config)
class ParametrosAdmin(ConstanceAdmin, ModelAdmin):
    # solo el administrador abre y modifica los parámetros; el moderador no tiene acceso.
    def has_module_permission(self, request):
        return es_administrador(request)

    def has_view_permission(self, request, obj=None):
        return es_administrador(request)

    def has_change_permission(self, request, obj=None):
        return es_administrador(request)
