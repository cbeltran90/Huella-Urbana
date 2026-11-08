"""Listados públicos de publicaciones (CU-20): perdidos y disponibles."""

from django.contrib.gis.db.models.functions import Distance

from .models import Publicacion

Tipo = Publicacion.Tipo
TIPOS_PERDIDOS = (Tipo.EXTRAVIO, Tipo.HALLAZGO)


def perdidos(*, tipo="", especie="", tamano="", punto=None):
    """Publicaciones vigentes de extravío y hallazgo, con filtros.

    Con "punto" se ordenan de la más cercana a la más lejana; sin él, de la más nueva a la
    más vieja. "ubicacion" es siempre el punto que se puede mostrar, nunca un domicilio real.
    """
    publicaciones = Publicacion.objects.filter(
        estado=Publicacion.Estado.VIGENTE, tipo__in=TIPOS_PERDIDOS
    ).select_related("ficha")
    if tipo in TIPOS_PERDIDOS:
        publicaciones = publicaciones.filter(tipo=tipo)
    if especie:
        publicaciones = publicaciones.filter(especie=especie)
    if tamano:
        publicaciones = publicaciones.filter(tamano=tamano)
    if punto is not None:
        return publicaciones.annotate(distancia=Distance("ubicacion", punto)).order_by("distancia")
    return publicaciones.order_by("-fecha")
