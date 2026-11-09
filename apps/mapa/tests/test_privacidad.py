"""El mapa nunca muestra el punto exacto de un domicilio (RNF3, Ley 25.326)."""

import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse
from model_bakery import baker

from apps.cuentas import geo
from apps.cuentas.servicios import guardar_domicilio
from apps.fichas.models import FichaAnimal
from apps.publicaciones.servicios import publicar_extravio

CASA = Point(-68.3040, -54.8025, srid=4326)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def desplazamiento_fijo(monkeypatch):
    # El desplazamiento real es al azar: uno fijo hace que el resultado sea previsible.
    monkeypatch.setattr(geo, "desplazar", lambda lon, lat, radio: (lon + 0.001, lat + 0.001))


def test_un_extravio_desde_el_domicilio_va_al_mapa_con_el_punto_desplazado(client, ana):
    guardar_domicilio(ana, CASA)
    publicar_extravio(ana, ficha=baker.make(FichaAnimal, especie="perro"))

    respuesta = client.get(reverse("mapa:datos"))

    (punto,) = respuesta.json()["features"]
    assert punto["geometry"]["coordinates"] == [-68.303, -54.8015]
    texto = respuesta.content.decode()
    assert "-68.304" not in texto and "-54.8025" not in texto
