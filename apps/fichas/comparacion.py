from constance import config
from django.db.models import Q

from apps.imagenes import vision
from apps.imagenes.models import Fotografia
from apps.publicaciones.models import Publicacion

from .models import FichaAnimal

# Un extravío se compara con hallazgos y un hallazgo con extravíos.
_OPUESTO = {
    Publicacion.Tipo.EXTRAVIO: Publicacion.Tipo.HALLAZGO,
    Publicacion.Tipo.HALLAZGO: Publicacion.Tipo.EXTRAVIO,
}


def _igual(a, b):
    return bool(a) and bool(b) and str(a).strip().lower() == str(b).strip().lower()


def contar_atributos(publicacion, ficha):
    """Cuántos de especie, tamaño, raza y color coinciden (los vacíos no cuentan)."""
    pares = [
        (publicacion.especie, ficha.especie),
        (publicacion.tamano, ficha.tamano),
        (publicacion.raza, ficha.raza),
        (publicacion.color, ficha.color),
    ]
    return sum(_igual(a, b) for a, b in pares)


def _embeddings(ficha):
    fotos = Fotografia.objects.filter(ficha=ficha, embedding__isnull=False)
    return [vision.desde_bytes(bytes(f.embedding)) for f in fotos]


def similitud_visual(publicacion, ficha):
    """Mayor similitud coseno entre las fotos de ambas fichas; None si falta alguna."""
    propias = _embeddings(publicacion.ficha) if publicacion.ficha_id else []
    ajenas = _embeddings(ficha)
    if not propias or not ajenas:
        return None
    return max(vision.similitud_coseno(a, b) for a in propias for b in ajenas)


def buscar_candidatas(publicacion):
    """Lista de (ficha, atributos, similitud) ordenada de mejor a peor.

    Entra una ficha si la especie coincide y además coinciden otro atributo o la similitud
    visual supera UMBRAL_SIMILITUD. Solo cuentan fichas con una publicación vigente opuesta.
    """
    opuesto = _OPUESTO.get(publicacion.tipo)
    if opuesto is None:
        return []
    por_publicacion = Q(
        publicaciones__tipo=opuesto, publicaciones__estado=Publicacion.Estado.VIGENTE
    )
    if publicacion.tipo == Publicacion.Tipo.HALLAZGO:
        # Quien perdió al animal puede no haber publicado el extravío todavía: sus fichas
        # registradas (incluso las privadas) también son candidatas de un hallazgo.
        por_publicacion |= Q(estado=FichaAnimal.Estado.REGISTRADO)
    fichas = (
        FichaAnimal.objects.filter(por_publicacion, especie=publicacion.especie)
        .exclude(pk=publicacion.ficha_id)
        .distinct()
    )
    resultado = []
    for ficha in fichas:
        atributos = contar_atributos(publicacion, ficha)
        similitud = similitud_visual(publicacion, ficha)
        if atributos >= 2 or (similitud is not None and similitud >= config.UMBRAL_SIMILITUD):
            resultado.append((ficha, atributos, similitud))
    resultado.sort(key=lambda c: (c[2] if c[2] is not None else -1, c[1]), reverse=True)
    return resultado
