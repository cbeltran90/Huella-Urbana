"""Listados públicos de publicaciones (CU-20): perdidos y disponibles."""

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point

from apps.cuentas import geo

from .models import Publicacion

Tipo = Publicacion.Tipo
TIPOS_PERDIDOS = (Tipo.EXTRAVIO, Tipo.HALLAZGO)
TIPOS_DISPONIBLES = (Tipo.ADOPCION, Tipo.TRANSITO)


def _vigentes(tipos, *, tipo, especie, tamano):
    """Las vigentes de esos tipos, con los filtros que vengan con valor."""
    publicaciones = Publicacion.objects.filter(
        estado=Publicacion.Estado.VIGENTE, tipo__in=tipos
    ).select_related("ficha")
    if tipo in tipos:
        publicaciones = publicaciones.filter(tipo=tipo)
    if especie:
        publicaciones = publicaciones.filter(especie=especie)
    if tamano:
        publicaciones = publicaciones.filter(tamano=tamano)
    return publicaciones


def perdidos(*, tipo="", especie="", tamano="", punto=None):
    """Publicaciones vigentes de extravío y hallazgo, con filtros.

    Con "punto" se ordenan de la más cercana a la más lejana; sin él, de la más nueva a la
    más vieja. "ubicacion" es siempre el punto que se puede mostrar, nunca un domicilio real.
    """
    publicaciones = _vigentes(TIPOS_PERDIDOS, tipo=tipo, especie=especie, tamano=tamano)
    if punto is not None:
        return publicaciones.annotate(distancia=Distance("ubicacion", punto)).order_by("distancia")
    return publicaciones.order_by("-fecha")


def disponibles(*, tipo="", especie="", tamano=""):
    """Publicaciones vigentes de adopción y tránsito, con filtros, de la más nueva a la más vieja.

    CU-20 pide orden por cercanía solo en perdidos.
    """
    return _vigentes(TIPOS_DISPONIBLES, tipo=tipo, especie=especie, tamano=tamano).order_by(
        "-fecha"
    )


def punto_desde(lat, lon):
    """El punto elegido en el mapa, o None si falta, no es un número o cae fuera de la zona."""
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not geo.en_zona(lon, lat):
        return None
    return Point(lon, lat, srid=4326)
