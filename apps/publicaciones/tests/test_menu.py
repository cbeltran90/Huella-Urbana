import re

import pytest
from django.urls import reverse
from model_bakery import baker

from apps.fichas.models import Coincidencia, FichaAnimal
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db


def test_el_menu_muestra_los_enlaces_y_el_contador(entrar, ana, beto):
    ficha = baker.make(FichaAnimal, responsable=ana)
    hallazgo = hacer_publicacion(beto, tipo=Publicacion.Tipo.HALLAZGO, ficha=None)
    baker.make(Coincidencia, publicacion=hallazgo, ficha=ficha, elegida_por_autor=True)

    html = entrar(ana).get(reverse("core:inicio")).content.decode()

    assert "Mis fichas" in html and "Publicar hallazgo" in html and "Coincidencias" in html
    assert re.search(r'id="coincidencias-pendientes"[^>]*>\s*1\s*<', html)


def test_el_menu_sin_pendientes_no_muestra_contador(entrar, ana):
    html = entrar(ana).get(reverse("core:inicio")).content.decode()
    assert "Coincidencias" in html and "coincidencias-pendientes" not in html


def test_el_menu_sin_sesion_solo_ofrece_ingresar(client):
    html = client.get(reverse("core:inicio")).content.decode()
    assert "Ingresar" in html and "Mis fichas" not in html
