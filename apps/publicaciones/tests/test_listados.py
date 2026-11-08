from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.publicaciones import listados
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

Tipo = Publicacion.Tipo
CENTRO = Point(-68.3040, -54.8025, srid=4326)
CERCA = Point(-68.3050, -54.8030, srid=4326)
LEJOS = Point(-68.2000, -54.8000, srid=4326)

pytestmark = pytest.mark.django_db


def test_solo_lista_extravios_y_hallazgos_vigentes(ana):
    extravio = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO)
    hallazgo = hacer_publicacion(ana, tipo=Tipo.HALLAZGO)
    hacer_publicacion(ana, tipo=Tipo.ADOPCION)
    hacer_publicacion(ana, tipo=Tipo.AVISTAMIENTO)
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, estado=Publicacion.Estado.RESUELTA)
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, estado=Publicacion.Estado.ELIMINADA)

    assert set(listados.perdidos()) == {extravio, hallazgo}


def test_filtra_por_tipo_especie_y_tamano(ana):
    buscado = hacer_publicacion(ana, tipo=Tipo.HALLAZGO, especie="perro", tamano="grande")
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, especie="perro", tamano="grande")
    hacer_publicacion(ana, tipo=Tipo.HALLAZGO, especie="gato", tamano="grande")
    hacer_publicacion(ana, tipo=Tipo.HALLAZGO, especie="perro", tamano="pequeno")

    resultado = listados.perdidos(tipo=Tipo.HALLAZGO, especie="perro", tamano="grande")

    assert list(resultado) == [buscado]


def test_un_tipo_de_otro_listado_se_ignora(ana):
    extravio = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO)
    assert list(listados.perdidos(tipo=Tipo.ADOPCION)) == [extravio]


def test_con_un_punto_ordena_por_cercania(ana):
    lejos = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ubicacion=LEJOS)
    cerca = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ubicacion=CERCA)

    resultado = list(listados.perdidos(punto=CENTRO))

    assert resultado == [cerca, lejos]
    assert resultado[0].distancia.m < resultado[1].distancia.m


def test_sin_punto_ordena_de_la_mas_nueva_a_la_mas_vieja(ana):
    ahora = timezone.now()
    vieja = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, fecha=ahora - timedelta(days=2))
    nueva = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, fecha=ahora)

    assert list(listados.perdidos()) == [nueva, vieja]
