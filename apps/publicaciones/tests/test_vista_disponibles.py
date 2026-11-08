import re

import pytest
from django.urls import reverse

from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

Tipo = Publicacion.Tipo
DISPONIBLES = reverse("publicaciones:disponibles")

pytestmark = pytest.mark.django_db


def test_un_visitante_ve_las_adopciones_y_los_transitos(client, ana):
    hacer_publicacion(ana, tipo=Tipo.ADOPCION, color="negro")
    hacer_publicacion(ana, tipo=Tipo.TRANSITO, color="blanco")
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, color="marrón")

    respuesta = client.get(DISPONIBLES)
    html = respuesta.content.decode()

    assert respuesta.status_code == 200
    assert "negro" in html and "blanco" in html
    assert "marrón" not in html


def test_los_filtros_se_aplican_y_quedan_elegidos(client, ana):
    hacer_publicacion(ana, tipo=Tipo.ADOPCION, especie="perro", color="negro")
    hacer_publicacion(ana, tipo=Tipo.ADOPCION, especie="gato", color="gris")

    html = client.get(DISPONIBLES, {"especie": "gato"}).content.decode()

    assert "gris" in html and "negro" not in html
    assert re.search(r'<option value="gato"\s+selected>', html)


def test_no_tiene_mapa_ni_distancia_aunque_vengan_coordenadas(client, ana):
    hacer_publicacion(ana, tipo=Tipo.ADOPCION)

    html = client.get(DISPONIBLES, {"lat": "-54.8025", "lon": "-68.3040"}).content.decode()

    assert "mapa-cercania" not in html
    assert " a 0 m" not in html


def test_sin_resultados_lo_dice(client):
    html = client.get(DISPONIBLES).content.decode()
    assert "No hay resultados para esos filtros." in html
