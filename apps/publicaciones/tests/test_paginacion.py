import pytest
from django.urls import reverse

from apps.publicaciones.models import Publicacion
from apps.publicaciones.views import POR_PAGINA

from .conftest import hacer_publicacion

Tipo = Publicacion.Tipo
PERDIDOS = reverse("publicaciones:perdidos")
HTMX = {"HTTP_HX_REQUEST": "true"}

pytestmark = pytest.mark.django_db


def tarjetas(html):
    return html.count('<li class="rounded-lg')


def test_la_primera_pagina_muestra_el_tope_y_ver_mas(client, ana):
    for _ in range(POR_PAGINA + 1):
        hacer_publicacion(ana, tipo=Tipo.EXTRAVIO)

    html = client.get(PERDIDOS).content.decode()

    assert tarjetas(html) == POR_PAGINA
    assert "Ver más" in html


def test_con_htmx_devuelve_solo_las_tarjetas_de_la_pagina(client, ana):
    for _ in range(POR_PAGINA + 1):
        hacer_publicacion(ana, tipo=Tipo.EXTRAVIO)

    html = client.get(PERDIDOS, {"pagina": 2}, **HTMX).content.decode()

    assert tarjetas(html) == 1
    assert "<html" not in html
    assert "Ver más" not in html


def test_ver_mas_conserva_los_filtros(client, ana):
    for _ in range(POR_PAGINA + 1):
        hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, especie="perro")

    html = client.get(PERDIDOS, {"especie": "perro"}).content.decode()

    assert "especie=perro&pagina=2" in html


def test_una_pagina_invalida_muestra_la_primera(client, ana):
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO)
    respuesta = client.get(PERDIDOS, {"pagina": "abc"})

    assert respuesta.status_code == 200
    assert tarjetas(respuesta.content.decode()) == 1


def test_el_menu_muestra_los_listados_tambien_al_visitante(client):
    html = client.get(reverse("core:inicio")).content.decode()

    assert reverse("publicaciones:perdidos") in html
    assert reverse("publicaciones:disponibles") in html
