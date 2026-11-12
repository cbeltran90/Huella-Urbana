import pytest
from django.conf import settings
from django.urls import reverse

from apps.transito.models import Postulacion

from .conftest import BACKEND_MODELO, con_perfil, hacer_ficha

pytestmark = pytest.mark.django_db


def url(ficha):
    return reverse("adopcion:postulantes", args=[ficha.pk])


def postular(ficha, usuario, tipo=Postulacion.Tipo.ADOPCION, contacto="2901 444444"):
    return Postulacion.objects.create(ficha=ficha, usuario=usuario, tipo=tipo, contacto=contacto)


@pytest.fixture
def entrar(client):
    def _entrar(usuario):
        client.force_login(usuario, backend=BACKEND_MODELO)
        return client

    return _entrar


def test_hay_que_iniciar_sesion(client):
    respuesta = client.get(url(hacer_ficha()))

    assert respuesta.status_code == 302
    assert respuesta.url.startswith(settings.LOGIN_URL)


def test_una_ficha_privada_no_existe_para_los_demas(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto, es_privada=True)

    assert entrar(ana).get(url(ficha)).status_code == 404


def test_quien_no_elige_no_puede_ver_a_los_postulantes(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto)

    assert entrar(ana).get(url(ficha)).status_code == 403


def test_quien_elige_ve_a_los_postulantes_con_su_hogar(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    postular(ficha, con_perfil(ana), contacto="ana por whatsapp")

    html = entrar(beto).get(url(ficha)).content.decode()

    assert "Ana" in html
    assert "ana por whatsapp" in html
    assert "Tuve perros toda la vida." in html


def test_no_muestra_las_postulaciones_de_transito(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    postular(ficha, con_perfil(ana), Postulacion.Tipo.TRANSITO, contacto="ana por whatsapp")

    html = entrar(beto).get(url(ficha)).content.decode()

    assert "ana por whatsapp" not in html


def test_muestra_las_dudas_de_compatibilidad(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    postular(ficha, con_perfil(ana, hay_ninos=True))

    html = entrar(beto).get(url(ficha)).content.decode()

    assert "En el hogar viven niños y no sabemos si esta mascota se lleva bien con ellos." in html


def test_sin_postulantes_lo_dice(entrar, beto):
    html = entrar(beto).get(url(hacer_ficha(cuidador=beto))).content.decode()

    assert "Todavía no se postuló nadie." in html


def test_si_ya_eligio_muestra_a_quien(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    elegida = postular(ficha, con_perfil(ana), contacto="ana por whatsapp")
    elegida.estado = Postulacion.Estado.ELEGIDA
    elegida.save()

    html = entrar(beto).get(url(ficha)).content.decode()

    assert "Elegiste a Ana" in html
    assert "ana por whatsapp" in html
