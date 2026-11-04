import math

import pytest
from django.contrib.gis.geos import Point

from apps.cuentas.models import Domicilio
from apps.cuentas.servicios import DomicilioInvalido, guardar_domicilio
from apps.publicaciones import ubicacion

pytestmark = pytest.mark.django_db

EXACTO = Point(-68.3030, -54.8019, srid=4326)


def metros(a, b):
    """Distancia aproximada entre dos puntos cercanos (equirectangular)."""
    dx = math.radians(b.x - a.x) * math.cos(math.radians(a.y)) * 6_371_000
    dy = math.radians(b.y - a.y) * 6_371_000
    return math.hypot(dx, dy)


def test_un_usuario_sin_domicilio_no_tiene_punto(ana):
    assert ubicacion.punto_de_domicilio(ana) is None


def test_el_punto_del_domicilio_es_el_desplazado_no_el_exacto(ana):
    domicilio = guardar_domicilio(ana, EXACTO)

    punto = ubicacion.punto_de_domicilio(ana)

    assert punto.equals_exact(domicilio.ubicacion_desplazada, 1e-9)
    assert not punto.equals_exact(EXACTO, 1e-9)


def test_registrar_domicilio_lo_guarda_y_devuelve_el_punto_desplazado(ana):
    mostrado = ubicacion.registrar_domicilio(ana, EXACTO)

    assert Domicilio.objects.get(usuario=ana).ubicacion.equals_exact(EXACTO, 1e-9)
    assert 0 < metros(EXACTO, mostrado) <= 151


def test_un_punto_fuera_de_la_zona_no_se_guarda(ana):
    fuera = Point(-58.38, -34.60, srid=4326)  # Buenos Aires

    with pytest.raises(DomicilioInvalido):
        ubicacion.registrar_domicilio(ana, fuera)

    assert not Domicilio.objects.exists()
