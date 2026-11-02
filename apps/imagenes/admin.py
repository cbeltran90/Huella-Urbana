from django.contrib import admin

from .models import Fotografia


@admin.register(Fotografia)
class FotografiaAdmin(admin.ModelAdmin):
    list_display = ("id", "ficha", "tiene_animal", "motivo_revision", "revisada_por")
    list_filter = ("motivo_revision", "tiene_animal")
    readonly_fields = ("archivo", "hash_sha256", "hash_perceptual")
