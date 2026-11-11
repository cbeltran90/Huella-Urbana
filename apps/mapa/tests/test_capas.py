import pytest
from django.contrib.gis.geos import Point

from apps.mapa import capas
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

Tipo, Estado = Publicacion.Tipo, Publicacion.Estado

pytestmark = pytest.mark.django_db


def test_cada_tipo_va_en_su_capa(ana):
    extravio = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO)
    hallazgo = hacer_publicacion(ana, tipo=Tipo.HALLAZGO)
    adopcion = hacer_publicacion(ana, tipo=Tipo.ADOPCION)
    transito = hacer_publicacion(ana, tipo=Tipo.TRANSITO)

    puntos = capas.geojson()["features"]

    assert {p["properties"]["id"]: p["properties"]["capa"] for p in puntos} == {
        extravio.pk: "perdidos",
        hallazgo.pk: "perdidos",
        adopcion.pk: "adopcion",
        transito.pk: "adopcion",
    }


def test_solo_muestra_lo_vigente_y_nunca_avistamientos(ana):
    vigente = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO)
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, estado=Estado.RESUELTA)
    hacer_publicacion(ana, tipo=Tipo.ADOPCION, estado=Estado.ELIMINADA)
    hacer_publicacion(ana, tipo=Tipo.SILVESTRE)

    puntos = capas.geojson()["features"]

    assert [p["properties"]["id"] for p in puntos] == [vigente.pk]


def test_el_punto_va_en_longitud_latitud(ana):
    hacer_publicacion(ana, ubicacion=Point(-68.3040, -54.8025, srid=4326))

    (punto,) = capas.geojson()["features"]

    assert punto["geometry"] == {"type": "Point", "coordinates": [-68.304, -54.8025]}


def test_cada_capa_tiene_su_leyenda():
    assert capas.LEYENDAS.keys() == capas.CAPAS.keys()
