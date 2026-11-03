from django.contrib import admin

from .models import Publicacion


@admin.register(Publicacion)
class PublicacionAdmin(admin.ModelAdmin):
    list_display = ("id", "tipo", "estado", "autor", "ficha", "fecha")
    list_filter = ("tipo", "estado")
    search_fields = ("descripcion", "autor__nombre_usuario")
