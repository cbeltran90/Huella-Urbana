from django import forms

from apps.publicaciones.forms import VALIDAR_TELEFONO


class ElegirForm(forms.Form):
    """Confirmar la elección; el teléfono va solo en el aviso a la persona elegida (CU-29)."""

    telefono = forms.CharField(
        label="Teléfono para coordinar la entrega",
        required=False,
        max_length=30,
        validators=[VALIDAR_TELEFONO],
        help_text="Opcional. Solo lo ve la persona que elijas.",
    )
