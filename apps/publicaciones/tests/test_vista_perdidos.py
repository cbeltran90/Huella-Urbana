import re

import pytest
from django.urls import reverse
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

Tipo = Publicacion.Tipo
PERDIDOS = reverse("publicaciones:perdidos")

pytestmark = pytest.mark.django_db


def test_un_visitante_ve_el_listado(client, ana):
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, especie="perro")

    respuesta = client.get(PERDIDOS)

    assert respuesta.status_code == 200
    assert "Extravío" in respuesta.content.decode()


def test_los_filtros_se_aplican_y_quedan_elegidos(client, ana):
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, especie="perro", color="marrón")
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, especie="gato", color="gris")

    html = client.get(PERDIDOS, {"especie": "gato"}).content.decode()

    assert "gris" in html and "marrón" not in html
    assert re.search(r'<option value="gato"\s+selected>', html)


def test_con_punto_muestra_la_distancia(client, ana):
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO)

    html = client.get(PERDIDOS, {"lat": "-54.8025", "lon": "-68.3040"}).content.decode()

    assert " m<" in html or " m\n" in html


def test_un_punto_invalido_no_rompe_la_pagina(client, ana):
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO)
    assert client.get(PERDIDOS, {"lat": "abc", "lon": "xyz"}).status_code == 200


def test_sin_resultados_lo_dice(client):
    html = client.get(PERDIDOS, {"especie": "gato"}).content.decode()
    assert "No hay resultados para esos filtros." in html


def test_una_ficha_privada_no_muestra_el_nombre(client, ana):
    privada = baker.make(FichaAnimal, especie="gato", nombre="Secreta", es_privada=True)
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=privada)

    assert "Secreta" not in client.get(PERDIDOS).content.decode()


def test_la_tarjeta_lleva_a_la_ficha_si_es_publica_y_si_no_a_la_publicacion(client, ana):
    publica = baker.make(FichaAnimal, especie="perro", es_privada=False)
    privada = baker.make(FichaAnimal, especie="perro", es_privada=True)
    con_publica = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=publica)
    con_privada = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=privada)
    sin_ficha = hacer_publicacion(ana, tipo=Tipo.HALLAZGO, ficha=None)

    html = client.get(PERDIDOS).content.decode()

    assert reverse("fichas:detalle", args=[publica.pk]) in html
    assert reverse("fichas:detalle", args=[privada.pk]) not in html
    assert reverse("publicaciones:detalle", args=[con_privada.pk]) in html
    assert reverse("publicaciones:detalle", args=[sin_ficha.pk]) in html
    assert reverse("publicaciones:detalle", args=[con_publica.pk]) not in html


def test_ofrece_elegir_entre_extravio_y_hallazgo(client):
    assert 'name="tipo"' in client.get(PERDIDOS).content.decode()
