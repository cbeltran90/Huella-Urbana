"""De dónde sale el punto de una publicación."""

import math
import random

from constance import config
from django.apps import apps as django_apps
from django.contrib.gis.geos import Point

_AZAR = random.SystemRandom()
_METROS_POR_GRADO = 111_320


def desplazar(lon, lat, radio_metros, azar=_AZAR):
    """Punto al azar dentro de "radio_metros" del original (uniforme en el círculo)."""
    distancia = radio_metros * math.sqrt(azar.random())
    angulo = azar.random() * 2 * math.pi
    dlat = distancia * math.cos(angulo) / _METROS_POR_GRADO
    dlon = distancia * math.sin(angulo) / (_METROS_POR_GRADO * math.cos(math.radians(lat)))
    return lon + dlon, lat + dlat


def punto_de_domicilio(usuario):
    """Punto desplazado del domicilio del usuario, o None si no tiene (o "Domicilio" no existe)."""
    try:
        domicilio = django_apps.get_model("cuentas", "Domicilio")
    except LookupError:
        return None
    registro = domicilio.objects.filter(usuario=usuario).first()
    return registro.ubicacion_desplazada if registro else None


def registrar_domicilio(usuario, punto):
    """Guarda "punto" como domicilio del usuario y devuelve el punto desplazado."""
    try:
        from apps.cuentas.servicios import guardar_domicilio
    except ImportError:
        lon, lat = desplazar(punto.x, punto.y, config.RADIO_DOMICILIO_METROS)
        return Point(lon, lat, srid=4326)
    return guardar_domicilio(usuario, punto).ubicacion_desplazada
