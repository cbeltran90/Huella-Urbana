from django import forms

from apps.core.filtros import NoOfensivo
from apps.fichas.forms import CLASE_CAMPO, MENSAJE_TEXTO_OFENSIVO
from apps.fichas.models import FichaAnimal

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
