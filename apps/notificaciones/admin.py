from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Notificacion


@admin.register(Notificacion)
class NotificacionAdmin(ModelAdmin):
    list_display = ("titulo", "usuario", "tipo", "leida", "creada_at", "push_enviado_at")
    list_filter = ("tipo", "leida")
    search_fields = ("titulo", "usuario_email", "usuario__nombre_usuario")
    raw_id_fields = ("usuario", "ficha")
    readonly_fields = ("creada_at", "push_enviado_at", "reintentos")
    list_select_related = ("usuario",)
    date_hierarchy = "creada_at"
