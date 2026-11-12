from django import forms

from apps.core.filtros import NoOfensivo
from apps.imagenes.forms import MAX_FOTOS, TIPOS_DE_IMAGEN, CampoVariosArchivos

from .models import FichaAnimal
from .servicios import CAMPOS_EDITABLES

MENSAJE_TEXTO_OFENSIVO = "Texto ofensivo"
MENSAJE_EDAD = "La edad debe ser un número de años, entre 0 y 30"

CAMPOS_SI_NO = (
    "castrado",
    "desparasitado",
    "vacunado",
    "requiere_medicacion",
    "problemas_conducta",
    "compatible_ninos",
    "compatible_animales",
)
CAMPOS_CON_TEXTO_LIBRE = ("nombre", "color", "raza", "temperamento")

CLASE_CAMPO = "mt-1 min-h-11 w-full rounded border border-stone-300 px-3 py-2"
CLASE_CASILLA = "size-5"


class FichaForm(forms.ModelForm):
    """Datos del animal para el alta preventiva y la edición."""

    edad_estimada = forms.IntegerField(
        label="Edad estimada (años)",
        required=False,
        min_value=0,
        max_value=30,
        error_messages={
            "invalid": MENSAJE_EDAD,
            "min_value": MENSAJE_EDAD,
            "max_value": MENSAJE_EDAD,
        },
    )

    class Meta:
        model = FichaAnimal
        fields = CAMPOS_EDITABLES
        labels = {
            "castrado": "Castrado",
            "desparasitado": "Desparasitado",
            "vacunado": "Vacunado",
            "chip": "Número de chip",
            "requiere_medicacion": "Requiere medicación",
            "problemas_conducta": "Tiene problemas de conducta",
            "compatible_ninos": "Se lleva bien con niños",
            "compatible_animales": "Se lleva bien con otros animales",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre in CAMPOS_CON_TEXTO_LIBRE:
            self.fields[nombre].validators.append(NoOfensivo(MENSAJE_TEXTO_OFENSIVO))
        for nombre, campo in self.fields.items():
            es_casilla = nombre in CAMPOS_SI_NO
            campo.widget.attrs["class"] = CLASE_CASILLA if es_casilla else CLASE_CAMPO

    def clean_edad_estimada(self):
        # El modelo guarda texto: sin edad se guarda vacío, no None.
        edad = self.cleaned_data["edad_estimada"]
        return "" if edad is None else str(edad)

    def campos_datos(self):
        return [self[nombre] for nombre in self.fields if nombre not in CAMPOS_SI_NO]

    def campos_si_no(self):
        return [self[nombre] for nombre in CAMPOS_SI_NO]


MENSAJE_MUCHAS_FOTOS = f"Podés subir hasta {MAX_FOTOS} fotos por vez"


class FichaConFotosForm(FichaForm):
    """La ficha de «Nueva ficha» y «Editar»: los datos del animal y, si querés, fotos."""

    fotos = CampoVariosArchivos(label="Fotos (opcional)", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fotos"].widget.attrs["accept"] = TIPOS_DE_IMAGEN

    def clean_fotos(self):
        fotos = self.cleaned_data["fotos"]
        if len(fotos) > MAX_FOTOS:
            raise forms.ValidationError(MENSAJE_MUCHAS_FOTOS)
        return fotos

    def campos_datos(self):
        return [campo for campo in super().campos_datos() if campo.name != "fotos"]
