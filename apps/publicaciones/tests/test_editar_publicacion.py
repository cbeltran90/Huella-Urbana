import pytest
from django.urls import reverse

from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

Tipo, Estado = Publicacion.Tipo, Publicacion.Estado

pytestmark = pytest.mark.django_db


def _editar(publicacion):
    return reverse("publicaciones:editar", args=[publicacion.pk])


def test_edita_la_descripcion(entrar, ana):
    publicacion = hacer_publicacion(ana, descripcion="Antes")

    respuesta = entrar(ana).post(_editar(publicacion), {"descripcion": "Después"})

    assert respuesta.status_code == 302
    assert respuesta.url == reverse("publicaciones:mis_publicaciones")
    publicacion.refresh_from_db()
    assert publicacion.descripcion == "Después"


def test_texto_ofensivo_se_rechaza(entrar, ana):
    publicacion = hacer_publicacion(ana, descripcion="Antes")

    respuesta = entrar(ana).post(_editar(publicacion), {"descripcion": "mierda"})

    assert respuesta.status_code == 200
    assert "Texto ofensivo" in respuesta.content.decode()
    publicacion.refresh_from_db()
    assert publicacion.descripcion == "Antes"


def test_en_adopcion_se_edita_el_telefono(entrar, ana):
    publicacion = hacer_publicacion(ana, tipo=Tipo.ADOPCION)

    entrar(ana).post(_editar(publicacion), {"descripcion": "", "telefono_visible": "2901 123456"})

    publicacion.refresh_from_db()
    assert publicacion.telefono_visible == "2901 123456"


def test_un_telefono_invalido_se_rechaza(entrar, ana):
    publicacion = hacer_publicacion(ana, tipo=Tipo.ADOPCION)

    respuesta = entrar(ana).post(_editar(publicacion), {"telefono_visible": "llamame"})

    assert "Ingresá un teléfono válido" in respuesta.content.decode()


@pytest.mark.parametrize("tipo", [Tipo.EXTRAVIO, Tipo.HALLAZGO, Tipo.TRANSITO])
def test_fuera_de_adopcion_no_hay_telefono(entrar, ana, tipo):
    publicacion = hacer_publicacion(ana, tipo=tipo)
    cliente = entrar(ana)

    assert 'name="telefono_visible"' not in cliente.get(_editar(publicacion)).content.decode()
    cliente.post(_editar(publicacion), {"descripcion": "", "telefono_visible": "2901 123456"})
    publicacion.refresh_from_db()
    assert publicacion.telefono_visible == ""


def test_la_de_otra_persona_da_404(entrar, ana, beto):
    publicacion = hacer_publicacion(beto)

    assert entrar(ana).get(_editar(publicacion)).status_code == 404


def test_una_resuelta_no_se_edita(entrar, ana):
    publicacion = hacer_publicacion(ana, estado=Estado.RESUELTA)

    assert entrar(ana).get(_editar(publicacion)).status_code == 404


def test_el_listado_lleva_a_editar(entrar, ana):
    publicacion = hacer_publicacion(ana)

    html = entrar(ana).get(reverse("publicaciones:mis_publicaciones")).content.decode()

    assert _editar(publicacion) in html
