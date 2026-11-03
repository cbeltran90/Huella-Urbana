"""Cálculos de ubicación del domicilio (CU-03, RNF3)."""

import math
import random

_AZAR = random.SystemRandom()
_METROS_POR_GRADO = 111_320

# Ushuaia y alrededores: rectángulo en longitud y latitud (SRID 4326).
LONGITUD_MIN, LONGITUD_MAX = -68.60, -68.10
LATITUD_MIN, LATITUD_MAX = -54.95, -54.70


def en_zona(lon, lat):
    """True si el punto cae dentro de Ushuaia y alrededores."""
    return LONGITUD_MIN <= lon <= LONGITUD_MAX and LATITUD_MIN <= lat <= LATITUD_MAX


def desplazar(lon, lat, radio_metros, azar=_AZAR):
    """Punto al azar dentro de "radio_metros" del original (uniforme en el círculo).

    "azar" se puede reemplazar en los tests por algo que devuelva valores fijos.
    """
    distancia = radio_metros * math.sqrt(azar.random())
    angulo = azar.random() * 2 * math.pi
    dlat = distancia * math.cos(angulo) / _METROS_POR_GRADO
    dlon = distancia * math.sin(angulo) / (_METROS_POR_GRADO * math.cos(math.radians(lat)))
    return lon + dlon, lat + dlat
