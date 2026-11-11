from django import forms
from django.core.validators import RegexValidator

from apps.core.filtros import NoOfensivo
from apps.fichas.forms import CLASE_CAMPO, CLASE_CASILLA, MENSAJE_TEXTO_OFENSIVO, FichaForm
from apps.fichas.models import FichaAnimal
from apps.fichas.servicios import CAMPOS_EDITABLES

from .models import Publicacion

MENSAJE_ESPECIE = "Elegí la especie"
MENSAJE_FOTO = "Subí una foto del animal"
MENSAJE_UBICACION = "Indicá tu ubicación en el mapa o con el GPS"

CAMPOS_ANIMAL = ("nombre", "especie", "tamano", "raza", "color")
_PASO_DE_CAMPO = {
    "ficha": 1,
    "foto": 2,
    "latitud": 3,
    "longitud": 3,
    "nombre": 4,
    "especie": 4,
    "tamano": 4,
    "raza": 4,
    "color": 4,
    "estado_aparente": 4,
    "descripcion": 4,
}


class ExtravioForm(forms.Form):
    """Los datos Publicar extravío, en una sola página por pasos."""

    ficha = forms.ModelChoiceField(
        label="Tu animal",
        queryset=FichaAnimal.objects.none(),
        required=False,
        empty_label="Cargar un animal nuevo",
    )
    foto = forms.FileField(label="Foto", required=False)
    latitud = forms.FloatField(required=False, min_value=-90, max_value=90)
    longitud = forms.FloatField(required=False, min_value=-180, max_value=180)
    nombre = forms.CharField(label="Nombre (opcional)", max_length=100, required=False)
    especie = forms.ChoiceField(
        label="Especie",
        choices=[("", "---------"), *FichaAnimal.Especie.choices],
        required=False,
    )
    tamano = forms.ChoiceField(
        label="Tamaño",
        choices=[("", "---------"), *FichaAnimal.Tamano.choices],
        required=False,
    )
    raza = forms.CharField(label="Raza", max_length=100, required=False)
    color = forms.CharField(label="Color", max_length=100, required=False)
    estado_aparente = forms.CharField(label="Estado aparente", max_length=100, required=False)
    descripcion = forms.CharField(
        label="Descripción",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, usuario, tiene_domicilio, **kwargs):
        super().__init__(*args, **kwargs)
        self.tiene_domicilio = tiene_domicilio
        self.fields["ficha"].queryset = FichaAnimal.objects.filter(responsable=usuario)
        for nombre in ("nombre", "raza", "color", "estado_aparente", "descripcion"):
            self.fields[nombre].validators.append(NoOfensivo(MENSAJE_TEXTO_OFENSIVO))
        for campo in self.fields.values():
            campo.widget.attrs["class"] = CLASE_CAMPO
        # Alpine: al elegir una ficha se ocultan los datos del animal nuevo.
        self.fields["ficha"].widget.attrs["x-on:change"] = "conFicha = $event.target.value !== ''"

    def clean(self):
        datos = super().clean()
        if not datos.get("ficha"):
            if not datos.get("especie") and "especie" not in self.errors:
                self.add_error("especie", MENSAJE_ESPECIE)
            if not datos.get("foto"):
                self.add_error("foto", MENSAJE_FOTO)
        sin_punto = datos.get("latitud") is None or datos.get("longitud") is None
        if not self.tiene_domicilio and sin_punto and "latitud" not in self.errors:
            self.add_error("latitud", MENSAJE_UBICACION)
        return datos

    def datos_animal(self):
        return {campo: self.cleaned_data[campo] for campo in CAMPOS_ANIMAL}

    def paso_con_error(self):
        """El paso del asistente donde hay que volver para corregir; el último si no hay error."""
        pasos = [_PASO_DE_CAMPO.get(campo, 5) for campo in self.errors]
        return min(pasos, default=5)


MENSAJE_UBICACION_HALLAZGO = "Indicá dónde lo encontraste en el mapa o con el GPS"

_PASO_HALLAZGO = {
    "foto": 1,
    "latitud": 2,
    "longitud": 2,
    "especie": 3,
    "tamano": 3,
    "raza": 3,
    "color": 3,
    "estado_aparente": 3,
    "descripcion": 3,
}


class HallazgoForm(forms.Form):
    """Los datos del asistente de "Publicar hallazgo"."""

    foto = forms.FileField(label="Foto", required=False)
    latitud = forms.FloatField(required=False, min_value=-90, max_value=90)
    longitud = forms.FloatField(required=False, min_value=-180, max_value=180)
    especie = forms.ChoiceField(
        label="Especie",
        choices=[("", "---------"), *FichaAnimal.Especie.choices],
        required=False,
    )
    tamano = forms.ChoiceField(
        label="Tamaño",
        choices=[("", "---------"), *FichaAnimal.Tamano.choices],
        required=False,
    )
    raza = forms.CharField(label="Raza", max_length=100, required=False)
    color = forms.CharField(label="Color", max_length=100, required=False)
    estado_aparente = forms.CharField(label="Estado aparente", max_length=100, required=False)
    descripcion = forms.CharField(
        label="Descripción",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    tiene_consigo = forms.BooleanField(label="Tengo al animal conmigo", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre in ("raza", "color", "estado_aparente", "descripcion"):
            self.fields[nombre].validators.append(NoOfensivo(MENSAJE_TEXTO_OFENSIVO))
        for nombre, campo in self.fields.items():
            campo.widget.attrs["class"] = (
                CLASE_CASILLA if nombre == "tiene_consigo" else CLASE_CAMPO
            )

    def clean(self):
        datos = super().clean()
        if not datos.get("foto"):
            self.add_error("foto", MENSAJE_FOTO)
        if not datos.get("especie") and "especie" not in self.errors:
            self.add_error("especie", MENSAJE_ESPECIE)
        sin_punto = datos.get("latitud") is None or datos.get("longitud") is None
        if sin_punto and "latitud" not in self.errors:
            self.add_error("latitud", MENSAJE_UBICACION_HALLAZGO)
        return datos

    def datos_animal(self):
        return {campo: self.cleaned_data[campo] for campo in ("especie", "tamano", "raza", "color")}

    def paso_con_error(self):
        """El paso del asistente donde hay que volver para corregir; el último si no hay error."""
        pasos = [_PASO_HALLAZGO.get(campo, 4) for campo in self.errors]
        return min(pasos, default=4)


MAX_FOTOS = 5
MENSAJE_FOTOS = "Subí al menos una foto del animal"
MENSAJE_MUCHAS_FOTOS = f"Podés subir hasta {MAX_FOTOS} fotos"
MENSAJE_TELEFONO = "Ingresá un teléfono válido"
VALIDAR_TELEFONO = RegexValidator(r"^[0-9+\-() ]{6,30}$", MENSAJE_TELEFONO)


_EXTRAS_ADOPCION = ("fotos", "latitud", "longitud", "descripcion", "telefono_visible")
_PASO_ADOPCION = {
    "fotos": 2,
    "latitud": 3,
    "longitud": 3,
    "descripcion": 4,
    "telefono_visible": 4,
}


class _VariosArchivos(forms.ClearableFileInput):
    allow_multiple_selected = True


class _CampoVariosArchivos(forms.FileField):
    """Un campo de archivos que acepta varios."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", _VariosArchivos())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        limpiar = super().clean
        archivos = data if isinstance(data, (list, tuple)) else [data]
        return [limpiar(archivo, initial) for archivo in archivos if archivo]


class AltaAdopcionForm(FichaForm):
    """Alta directa en adopción: los datos de la ficha más fotos, ubicación y publicación."""

    fotos = _CampoVariosArchivos(label="Fotos", required=False)
    latitud = forms.FloatField(required=False, min_value=-90, max_value=90)
    longitud = forms.FloatField(required=False, min_value=-180, max_value=180)
    descripcion = forms.CharField(
        label="Descripción",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    telefono_visible = forms.CharField(
        label="Teléfono visible (opcional)",
        max_length=30,
        required=False,
        validators=[VALIDAR_TELEFONO],
    )

    def __init__(self, *args, tiene_domicilio, **kwargs):
        super().__init__(*args, **kwargs)
        self.tiene_domicilio = tiene_domicilio
        self.fields["descripcion"].validators.append(NoOfensivo(MENSAJE_TEXTO_OFENSIVO))
        self.fields["fotos"].widget.attrs["accept"] = "image/jpeg,image/png,image/webp"

    def clean(self):
        datos = super().clean()
        fotos = datos.get("fotos") or []
        if not fotos and "fotos" not in self.errors:
            self.add_error("fotos", MENSAJE_FOTOS)
        if len(fotos) > MAX_FOTOS:
            self.add_error("fotos", MENSAJE_MUCHAS_FOTOS)
        sin_punto = datos.get("latitud") is None or datos.get("longitud") is None
        if not self.tiene_domicilio and sin_punto and "latitud" not in self.errors:
            self.add_error("latitud", MENSAJE_UBICACION)
        return datos

    def datos_ficha(self):
        return {campo: self.cleaned_data[campo] for campo in CAMPOS_EDITABLES}

    def campos_datos(self):
        return [campo for campo in super().campos_datos() if campo.name not in _EXTRAS_ADOPCION]

    def paso_con_error(self):
        """El paso del asistente donde hay que volver para corregir; el último si no hay error."""
        pasos = [_PASO_ADOPCION.get(campo, 1) for campo in self.errors]
        return min(pasos, default=4)


class EditarPublicacionForm(forms.ModelForm):
    """Lo que se puede cambiar de una publicación propia (CU-65): la descripción y, si es de
    adopción, el teléfono visible."""

    descripcion = forms.CharField(
        label="Descripción",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        validators=[NoOfensivo(MENSAJE_TEXTO_OFENSIVO)],
    )
    telefono_visible = forms.CharField(
        label="Teléfono visible (opcional)",
        max_length=30,
        required=False,
        validators=[VALIDAR_TELEFONO],
    )

    class Meta:
        model = Publicacion
        fields = ("descripcion", "telefono_visible")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.tipo != Publicacion.Tipo.ADOPCION:
            del self.fields["telefono_visible"]
        for campo in self.fields.values():
            campo.widget.attrs["class"] = CLASE_CAMPO
