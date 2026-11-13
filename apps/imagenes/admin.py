from django.contrib import admin, messages
from django.core.files.storage import default_storage
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from apps.cuentas.permisos_admin import es_moderador_o_administrador

from . import moderacion
from .models import Fotografia


class RevisionFilter(admin.SimpleListFilter):
    title = "revisión"
    parameter_name = "revision"

    def lookups(self, request, model_admin):
        return [("pendientes", "Pendientes de revisión"), ("revisadas", "Ya revisadas")]

    def queryset(self, request, queryset):
        if self.value() == "pendientes":
            return queryset.exclude(motivo_revision="")
        if self.value() == "revisadas":
            return queryset.filter(revisada_por__isnull=False)
        return queryset


@admin.register(Fotografia)
class FotografiaAdmin(ModelAdmin):
    """Fotografías: las ven el moderador y el administrador.

    Son solo de consulta. Lo único que se hace desde acá es marcar como revisada una foto
    marcada, que la aprueba y hace que vuelva a mostrarse.
    """

    list_display = (
        "id",
        "vista_previa",
        "ficha",
        "tiene_animal",
        "motivo_revision",
        "revisada_por",
    )
    list_filter = (RevisionFilter, "motivo_revision", "tiene_animal")
    readonly_fields = ("archivo", "hash_sha256", "hash_perceptual")
    actions = ["marcar_revisada"]

    @admin.display(description="Foto")
    def vista_previa(self, fotografia):
        if not fotografia.archivo:
            return "—"
        return format_html(
            '<img src="{}" alt="" style="height:64px;border-radius:4px">',
            default_storage.url(fotografia.archivo),
        )

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

    def has_revisar_permission(self, request):
        return es_moderador_o_administrador(request)

    @admin.action(description="Marcar revisada (aprobar)", permissions=["revisar"])
    def marcar_revisada(self, request, queryset):
        revisadas = 0
        for fotografia in queryset:
            if moderacion.marcar_revisada(fotografia, request.user):
                revisadas += 1
        if revisadas:
            self.message_user(request, f"Fotografías revisadas: {revisadas}.", messages.SUCCESS)
        else:
            self.message_user(
                request, "Esas fotografías no tenían marca de revisión.", messages.WARNING
            )
