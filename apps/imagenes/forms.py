from django import forms

MAX_FOTOS = 5
TIPOS_DE_IMAGEN = "image/jpeg,image/png,image/webp"


class VariosArchivos(forms.ClearableFileInput):
    allow_multiple_selected = True


class CampoVariosArchivos(forms.FileField):
    """Un campo de archivos que acepta varios."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", VariosArchivos())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        limpiar = super().clean
        archivos = data if isinstance(data, (list, tuple)) else [data]
        return [limpiar(archivo, initial) for archivo in archivos if archivo]
