import pytest
from django.urls import reverse

from apps.notificaciones.models import Notificacion
from apps.publicaciones.models import Publicacion
from apps.transito.models import Postulacion

from .conftest import BACKEND_MODELO, PUNTO, con_perfil, hacer_ficha

pytestmark = pytest.mark.django_db


def url(postulacion):
    return reverse("adopcion:elegir", args=[postulacion.pk])


def postular(ficha, usuario, tipo=Postulacion.Tipo.ADOPCION):
    return Postulacion.objects.create(
        ficha=ficha, usuario=usuario, tipo=tipo, contacto="2901 444444"
    )


@pytest.fixture
def entrar(client):
    def _entrar(usuario):
        client.force_login(usuario, backend=BACKEND_MODELO)
        return client

    return _entrar


def test_quien_no_elige_no_puede_elegir(entrar, ana, beto, carla):
    postulacion = postular(hacer_ficha(cuidador=beto), con_perfil(ana))

    assert entrar(carla).get(url(postulacion)).status_code == 403


def test_una_postulacion_de_transito_no_se_elige_aca(entrar, ana, beto):
    postulacion = postular(hacer_ficha(cuidador=beto), ana, Postulacion.Tipo.TRANSITO)

    assert entrar(beto).get(url(postulacion)).status_code == 404


def test_pide_confirmar_con_el_telefono_de_la_publicacion(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto, nombre="Firulais")
    Publicacion.objects.create(
        tipo=Publicacion.Tipo.ADOPCION,
        autor=beto,
        ficha=ficha,
        ubicacion=PUNTO,
        telefono_visible="2901 555555",
    )
    postulacion = postular(ficha, con_perfil(ana))

    html = entrar(beto).get(url(postulacion)).content.decode()

    assert "¿Elegir a Ana para adoptar a Firulais?" in html
    assert 'value="2901 555555"' in html
    assert Postulacion.objects.get().estado == Postulacion.Estado.PENDIENTE


def test_al_confirmar_elige_y_vuelve_a_los_postulantes(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    postulacion = postular(ficha, con_perfil(ana))

    respuesta = entrar(beto).post(url(postulacion), {"telefono": "2901 555555"})

    assert respuesta.url == reverse("adopcion:postulantes", args=[ficha.pk])
    assert Postulacion.objects.get().estado == Postulacion.Estado.ELEGIDA
    assert "2901 555555" in Notificacion.objects.get(usuario=ana).mensaje


def test_el_telefono_es_opcional(entrar, ana, beto):
    postulacion = postular(hacer_ficha(cuidador=beto), con_perfil(ana))

    entrar(beto).post(url(postulacion), {"telefono": ""})

    assert Postulacion.objects.get().estado == Postulacion.Estado.ELEGIDA


def test_con_un_telefono_invalido_no_elige(entrar, ana, beto):
    postulacion = postular(hacer_ficha(cuidador=beto), con_perfil(ana))

    html = entrar(beto).post(url(postulacion), {"telefono": "llamame"}).content.decode()

    assert "Ingresá un teléfono válido" in html
    assert Postulacion.objects.get().estado == Postulacion.Estado.PENDIENTE


def test_si_ya_eligio_lo_informa(entrar, ana, beto, carla):
    ficha = hacer_ficha(cuidador=beto)
    primera = postular(ficha, con_perfil(ana))
    segunda = postular(ficha, con_perfil(carla))
    entrar(beto).post(url(primera), {"telefono": ""})

    html = entrar(beto).post(url(segunda), {"telefono": ""}).content.decode()

    assert "Esa postulación ya no está pendiente." in html


def test_los_postulantes_tienen_su_boton_para_elegir(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    postulacion = postular(ficha, con_perfil(ana))

    html = entrar(beto).get(reverse("adopcion:postulantes", args=[ficha.pk])).content.decode()

    assert "Elegir a Ana" in html
    assert url(postulacion) in html
