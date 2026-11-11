import pytest
from django.urls import reverse

from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

Tipo, Estado = Publicacion.Tipo, Publicacion.Estado

pytestmark = pytest.mark.django_db


def _detalle(client, publicacion):
    return client.get(reverse("publicaciones:detalle", args=[publicacion.pk])).content.decode()


def test_un_visitante_puede_escribir_por_whatsapp(client, ana):
    publicacion = hacer_publicacion(ana, tipo=Tipo.ADOPCION, telefono_visible="2901 15 444444")

    html = _detalle(client, publicacion)

    assert "Para consultar, escribile al" in html
    assert 'href="https://wa.me/5492901444444"' in html
    assert "2901 15 444444" in html


def test_si_no_hay_whatsapp_ofrece_llamar(client, ana):
    publicacion = hacer_publicacion(ana, tipo=Tipo.ADOPCION, telefono_visible="+1 555 123 4567 89")

    html = _detalle(client, publicacion)

    assert "Para consultar, llamá al" in html
    assert 'href="tel:+1555123456789"' in html


def test_cuando_la_publicacion_se_cierra_el_telefono_deja_de_verse(client, ana):
    publicacion = hacer_publicacion(
        ana, tipo=Tipo.ADOPCION, telefono_visible="2901 444444", estado=Estado.RESUELTA
    )

    assert "Para consultar" not in _detalle(client, publicacion)


def test_sin_telefono_no_se_muestra_nada(client, ana):
    publicacion = hacer_publicacion(ana, tipo=Tipo.ADOPCION)

    assert "Para consultar" not in _detalle(client, publicacion)
