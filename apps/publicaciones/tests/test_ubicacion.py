import math

import pytest
from django.contrib.gis.geos import Point

from apps.publicaciones import ubicacion


def metros(a, b):
    """Distancia aproximada entre dos puntos cercanos (equirectangular)."""
    dx = math.radians(b.x - a.x) * math.cos(math.radians(a.y)) * 6_371_000
    dy = math.radians(b.y - a.y) * 6_371_000
    return math.hypot(dx, dy)


def test_el_punto_desplazado_queda_dentro_del_radio():
    original = (-68.3030, -54.8019)
    for _ in range(200):
        lon, lat = ubicacion.desplazar(*original, 150)
        assert metros(Point(*original), Point(lon, lat)) <= 151


def test_el_desplazamiento_es_al_azar():
    puntos = {ubicacion.desplazar(-68.3030, -54.8019, 150) for _ in range(20)}

    assert len(puntos) > 1


@pytest.mark.django_db
def test_un_usuario_sin_domicilio_no_tiene_punto(django_user_model):
    usuario = django_user_model.objects.create_user("x@ejemplo.com", "Equis", "clave-de-prueba-1")

    assert ubicacion.punto_de_domicilio(usuario) is None


@pytest.mark.django_db
def test_registrar_domicilio_devuelve_un_punto_cercano_pero_no_el_exacto(django_user_model):
    usuario = django_user_model.objects.create_user("y@ejemplo.com", "Ye", "clave-de-prueba-1")
    exacto = Point(-68.3030, -54.8019, srid=4326)

    mostrado = ubicacion.registrar_domicilio(usuario, exacto)

    assert mostrado.srid == 4326
    assert 0 < metros(exacto, mostrado) <= 151
