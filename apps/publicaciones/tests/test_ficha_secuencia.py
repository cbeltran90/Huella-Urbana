import pytest
from django.urls import reverse
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db


def test_un_visitante_ve_la_secuencia_de_una_ficha_publica(client, ana):
    ficha = baker.make(FichaAnimal, especie="perro", es_privada=False)
    extravio = hacer_publicacion(ana, ficha=ficha, tipo=Publicacion.Tipo.EXTRAVIO)
    eliminada = hacer_publicacion(ana, ficha=ficha, estado=Publicacion.Estado.ELIMINADA)

    html = client.get(reverse("fichas:detalle", args=[ficha.pk])).content.decode()

    assert "Publicaciones" in html
    assert reverse("publicaciones:detalle", args=[extravio.pk]) in html
    assert reverse("publicaciones:detalle", args=[eliminada.pk]) not in html


def test_una_ficha_sin_publicaciones_lo_dice(client):
    ficha = baker.make(FichaAnimal, especie="gato", es_privada=False)

    html = client.get(reverse("fichas:detalle", args=[ficha.pk])).content.decode()

    assert "Todavía no hay publicaciones de este animal." in html
