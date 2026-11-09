import pytest
from django.urls import reverse

from apps.mapa import capas

MAPA = reverse("mapa:mapa")

pytestmark = pytest.mark.django_db


def test_un_visitante_ve_el_mapa_con_una_casilla_por_capa(client):
    respuesta = client.get(MAPA)

    assert respuesta.status_code == 200
    html = respuesta.content.decode()
    for clave, leyenda in capas.LEYENDAS.items():
        assert f'value="{clave}"' in html
        assert leyenda["nombre"] in html


def test_la_pagina_le_indica_al_mapa_de_donde_sacar_los_datos(client):
    configuracion = client.get(MAPA).context["capas_config"]

    assert configuracion["datos_url"] == reverse("mapa:datos")
    assert configuracion["tipos"]["extravio"] == "Extravío"
    assert configuracion["resumen_url"] == reverse("mapa:resumen", args=[0])


def test_el_menu_lleva_al_mapa_tambien_al_visitante(client):
    html = client.get(reverse("core:inicio")).content.decode()

    assert reverse("mapa:mapa") in html
