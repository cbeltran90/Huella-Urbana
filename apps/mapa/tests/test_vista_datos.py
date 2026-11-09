import pytest
from django.urls import reverse

from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

DATOS = reverse("mapa:datos")

pytestmark = pytest.mark.django_db


def test_un_visitante_recibe_los_datos_como_geojson(client, ana):
    publicacion = hacer_publicacion(ana, tipo=Publicacion.Tipo.HALLAZGO)

    respuesta = client.get(DATOS)

    assert respuesta.status_code == 200
    assert respuesta["Content-Type"] == "application/geo+json"
    assert [p["properties"]["id"] for p in respuesta.json()["features"]] == [publicacion.pk]


def test_los_datos_no_aceptan_post(client):
    assert client.post(DATOS).status_code == 405


def test_sin_publicaciones_las_capas_quedan_vacias(client):
    assert client.get(DATOS).json() == {"type": "FeatureCollection", "features": []}
