from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Coincidencia, FichaAnimal


@admin.register(FichaAnimal)
class FichaAnimalAdmin(ModelAdmin):
    list_display = ("__str__", "especie", "estado", "responsable", "cuidador", "es_privada")
    list_filter = ("estado", "especie", "es_privada")
    search_fields = ("nombre", "chip")
    raw_id_fields = ("responsable", "cuidador", "fusionada_en")

    def get_readonly_fields(self, request, obj=None):
        # Al editar, el estado solo cambia con cambiar_estado(); al crear se puede elegir.
        if obj is not None:
            return ("estado",)
        return ()


@admin.register(Coincidencia)
class CoincidenciaAdmin(ModelAdmin):
    list_display = (
        "publicacion",
        "ficha",
        "atributos_coincidentes",
        "similitud_visual",
        "elegida_por_autor",
        "decision_responsable",
    )
    list_filter = ("decision_responsable", "elegida_por_autor")
    raw_id_fields = ("publicacion", "ficha")
