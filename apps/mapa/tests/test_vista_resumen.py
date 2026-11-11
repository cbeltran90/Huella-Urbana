import pytest
from django.urls import reverse
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

Tipo, Estado = Publicacion.Tipo, Publicacion.Estado

pytestmark = pytest.mark.django_db


def _resumen(client, publicacion):
    url = reverse("mapa:resumen", args=[publicacion.pk])
    return client.get(url, HTTP_HX_REQUEST="true")


def test_un_visitante_ve_el_resumen_con_enlace_a_la_publicacion(client, ana):
    publicacion = hacer_publicacion(ana, tipo=Tipo.HALLAZGO, especie="perro")

    respuesta = _resumen(client, publicacion)

    assert respuesta.status_code == 200
    html = respuesta.content.decode()
    assert "Hallazgo" in html
    assert reverse("publicaciones:detalle", args=[publicacion.pk]) in html


def test_muestra_la_ficha_solo_si_es_publica(client, ana):
    publica = baker.make(FichaAnimal, especie="perro", nombre="Firulais", es_privada=False)
    privada = baker.make(FichaAnimal, especie="gato", nombre="Secreta", es_privada=True)

    con_publica = _resumen(client, hacer_publicacion(ana, ficha=publica)).content.decode()
    con_privada = _resumen(client, hacer_publicacion(ana, ficha=privada)).content.decode()

    assert "Firulais" in con_publica
    assert reverse("fichas:detalle", args=[publica.pk]) in con_publica
    assert "Secreta" not in con_privada
    assert reverse("fichas:detalle", args=[privada.pk]) not in con_privada


@pytest.mark.parametrize(
    "campos",
    [{"estado": Estado.RESUELTA}, {"estado": Estado.ELIMINADA}, {"tipo": Tipo.SILVESTRE}],
)
def test_lo_que_no_esta_en_el_mapa_no_tiene_resumen(client, ana, campos):
    assert _resumen(client, hacer_publicacion(ana, **campos)).status_code == 404


def test_sin_htmx_lleva_al_detalle_completo(client, ana):
    publicacion = hacer_publicacion(ana)

    respuesta = client.get(reverse("mapa:resumen", args=[publicacion.pk]))

    assert respuesta.status_code == 302
    assert respuesta.url == reverse("publicaciones:detalle", args=[publicacion.pk])
