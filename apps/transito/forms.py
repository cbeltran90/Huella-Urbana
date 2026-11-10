from django import forms

from apps.fichas.models import FichaAnimal

from . import servicios


class PerfilTransitoForm(forms.Form):
    """Perfil de hogar de tránsito.

    La obligatoriedad y los rangos los decide el servicio, así el aviso lista a la vez todo
    lo que falta.
    """

    especies = forms.MultipleChoiceField(
        label="Especies que acepta",
        required=False,
        choices=FichaAnimal.Especie.choices,
        widget=forms.CheckboxSelectMultiple,
        error_messages={"invalid_choice": servicios.MENSAJE_ESPECIE_INVALIDA},
    )
    tamano_maximo = forms.ChoiceField(
        label="Tamaño máximo",
        required=False,
        choices=[("", "Elegí una opción"), *FichaAnimal.Tamano.choices],
        error_messages={"invalid_choice": servicios.MENSAJE_TAMANO_INVALIDO},
    )
    duracion_maxima_dias = forms.IntegerField(
        label="Duración máxima (días)",
        required=False,
        error_messages={"invalid": "Indicá la cantidad de días con un número"},
    )
    acepta_medicacion = forms.BooleanField(label="Acepto animales con medicación", required=False)
    acepta_conducta = forms.BooleanField(
        label="Acepto animales con problemas de conducta", required=False
    )
    disponibilidad = forms.TypedChoiceField(
        label="Disponibilidad",
        required=False,
        choices=[("True", "Disponible"), ("False", "En pausa")],
        coerce=lambda valor: valor == "True",
        empty_value=None,
        error_messages={"invalid_choice": "Elegí si estás disponible o en pausa"},
    )
    pausa_hasta = forms.DateField(
        label="Fecha de reanudación",
        required=False,
        error_messages={"invalid": "Indicá una fecha válida"},
    )
    cupo_declarado = forms.IntegerField(
        label="Cupo",
        required=False,
        error_messages={"invalid": "Indicá el cupo con un número"},
    )
    confirmar_exceso = forms.BooleanField(required=False)


class PostulacionForm(forms.Form):
    """Canal de contacto de la postulación; el servicio valida que no esté vacío ni sea largo."""

    contacto = forms.CharField(label="Canal de contacto", required=False)
