from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Adopcion


@admin.register(Adopcion)
class AdopcionAdmin(ModelAdmin):
    list_display = ("ficha", "adoptante", "entregado_por", "fecha")
    search_fields = ("ficha__nombre", "adoptante__email", "adoptante__nombre_usuario")
    raw_id_fields = ("ficha", "adoptante", "entregado_por")
    list_select_related = ("ficha", "adoptante", "entregado_por")
    date_hierarchy = "fecha"
