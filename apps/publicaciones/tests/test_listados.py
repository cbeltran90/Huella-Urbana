from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone
from model_bakery import baker

from apps.fichas.models import FichaAnimal
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


@pytest.mark.parametrize(
    ("lat", "lon"),
    [
        (None, None),  # sin punto
        ("abc", "-68.30"),  # no es un número
        ("-34.60", "-58.38"),  # Buenos Aires: fuera de la zona
        ("nan", "nan"),  # float() lo acepta, pero no es un lugar
    ],
)
def test_un_punto_invalido_no_se_usa(lat, lon):
    assert listados.punto_desde(lat, lon) is None


def test_un_punto_de_la_zona_se_usa_con_longitud_primero():
    punto = listados.punto_desde("-54.8025", "-68.3040")
    assert (punto.x, punto.y) == (-68.3040, -54.8025)


def test_disponibles_lista_solo_adopciones_vigentes(ana):
    adopcion = hacer_publicacion(ana, tipo=Tipo.ADOPCION)
    hacer_publicacion(ana, tipo=Tipo.TRANSITO)
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO)
    hacer_publicacion(ana, tipo=Tipo.ADOPCION, estado=Publicacion.Estado.RESUELTA)

    assert list(listados.disponibles()) == [adopcion]


def test_disponibles_filtra_por_especie(ana):
    perro = hacer_publicacion(ana, tipo=Tipo.ADOPCION, especie="perro")
    hacer_publicacion(ana, tipo=Tipo.ADOPCION, especie="gato")

    assert list(listados.disponibles(especie="perro")) == [perro]


def test_la_secuencia_va_de_la_mas_vieja_a_la_mas_nueva_sin_las_eliminadas(ana):
    ficha = baker.make(FichaAnimal, especie="perro")
    ahora = timezone.now()
    nueva = hacer_publicacion(ana, ficha=ficha, fecha=ahora)
    vieja = hacer_publicacion(
        ana,
        ficha=ficha,
        fecha=ahora - timedelta(days=3),
        estado=Publicacion.Estado.RESUELTA,
    )
    hacer_publicacion(ana, ficha=ficha, estado=Publicacion.Estado.ELIMINADA)
    hacer_publicacion(ana, ficha=baker.make(FichaAnimal, especie="gato"))

    assert list(listados.secuencia(ficha)) == [vieja, nueva]
