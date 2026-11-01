"""Filtro de contenido ofensivo

Es una lista simple de términos: compara palabras completas, así que no marca
"Putumayo" por contener "puto". Entiende mayúsculas, tildes, números por letras
(m13rd4), letras repetidas de más (puuuuto) y nombres pegados (JuanPuto).
No detecta insultos que no estén en la lista: se ajusta a mano.
"""

import re
import unicodedata

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible

# Lista inicial: en minúsculas y sin tildes. Se revisa y se amplía entre todos.
LISTA_OFENSIVA = (
    "puta",
    "puto",
    "putita",
    "putito",
    "hijodeputa",
    "hdp",
    "lpm",
    "ctm",
    "mierda",
    "sorete",
    "pelotudo",
    "pelotudito",
    "pelotudita",
    "pelotuda",
    "forro",
    "forra",
    "conchudo",
    "conchuda",
    "verga",
    "pija",
    "cagon",
    "cagona",
    "idiota",
    "imbecil",
    "estupido",
    "estupida",
    "mogolico",
    "mogolica",
    "maricon",
    "trolo",
    "trola",
    "culo",
    "choto",
    "tonto",
    "tonta",
    "boludo",
    "boluda",
    "boludito",
    "boludita",
    "catadordeglandes",
)
TERMINOS_OFENSIVOS = frozenset(LISTA_OFENSIVA)

_LETRAS_POR_NUMEROS = str.maketrans("013457@$", "oieastas")
_CAMEL = re.compile(r"(?<=[a-zñáéíóúü])(?=[A-ZÑÁÉÍÓÚÜ])")
_REPETIDAS = re.compile(r"(.)\1{2,}")


def _palabras(texto):
    """Divide el texto en palabras en minúsculas, sin tildes y con los números como letras."""
    texto = _CAMEL.sub(" ", str(texto))
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.findall(r"[a-z]+", texto.translate(_LETRAS_POR_NUMEROS))


def _variantes(palabra):
    """La palabra tal cual y sin las letras repetidas de más (puuuuto -> puto)."""
    yield palabra
    yield _REPETIDAS.sub(r"\1", palabra)
    yield _REPETIDAS.sub(r"\1\1", palabra)


def contiene_ofensivo(texto):
    """True si el texto tiene alguna palabra de la lista de términos ofensivos."""
    if not texto:
        return False
    return any(
        variante in TERMINOS_OFENSIVOS
        for palabra in _palabras(texto)
        for variante in _variantes(palabra)
    )


@deconstructible
class NoOfensivo:
    """Validador de formularios y modelos: rechaza texto ofensivo con el mensaje indicado."""

    def __init__(self, mensaje="Contenido ofensivo"):
        self.mensaje = mensaje

    def __call__(self, valor):
        if contiene_ofensivo(valor):
            raise ValidationError(self.mensaje, code="ofensivo")

    def __eq__(self, otro):
        return isinstance(otro, NoOfensivo) and self.mensaje == otro.mensaje
