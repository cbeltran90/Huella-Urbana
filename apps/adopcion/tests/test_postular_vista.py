import pytest
from django.conf import settings
from django.urls import reverse

from apps.fichas.models import FichaAnimal
from apps.transito.models import Postulacion

from .conftest import BACKEND_MODELO, con_perfil, hacer_ficha

pytestmark = pytest.mark.django_db


def url(ficha):
    return reverse("adopcion:postular", args=[ficha.pk])


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


def test_muestra_el_formulario(entrar, ana):
    html = entrar(con_perfil(ana)).get(url(hacer_ficha())).content.decode()

    assert "Postularme para adoptar" in html
    assert 'name="contacto"' in html


def test_al_postularse_vuelve_a_la_ficha(entrar, ana):
    ficha = hacer_ficha()

    respuesta = entrar(con_perfil(ana)).post(url(ficha), {"contacto": "2901 444444"})

    assert respuesta.url == f"{reverse('fichas:detalle', args=[ficha.pk])}?postulado_adopcion=1"
    assert Postulacion.objects.get().tipo == Postulacion.Tipo.ADOPCION


def test_sin_perfil_lleva_a_completarlo(entrar, ana):
    html = entrar(ana).get(url(hacer_ficha())).content.decode()

    assert "completá tu perfil de hogar y familia" in html
    assert reverse("cuentas:perfil_adoptante") in html
    assert 'name="contacto"' not in html


def test_sin_perfil_no_se_crea_nada_aunque_mande_el_formulario(entrar, ana):
    entrar(ana).post(url(hacer_ficha()), {"contacto": "2901 444444"})

    assert not Postulacion.objects.exists()


def test_sin_contacto_lo_pide_y_no_crea_nada(entrar, ana):
    respuesta = entrar(con_perfil(ana)).post(url(hacer_ficha()), {"contacto": ""})

    assert respuesta.status_code == 200
    assert "Indicá un canal de contacto." in respuesta.content.decode()
    assert not Postulacion.objects.exists()


def test_muestra_el_aviso_de_incompatibilidad(entrar, ana):
    html = entrar(con_perfil(ana, hay_ninos=True)).get(url(hacer_ficha())).content.decode()

    assert "no sabemos si esta mascota se lleva bien con ellos" in html
    assert 'name="contacto"' in html


def test_si_la_mascota_ya_no_busca_familia_lo_informa(entrar, ana):
    ficha = hacer_ficha(FichaAnimal.Estado.REGISTRADO)

    html = entrar(con_perfil(ana)).get(url(ficha)).content.decode()

    assert "Esta mascota ya no busca familia." in html
    assert 'name="contacto"' not in html


def test_una_ficha_privada_no_existe_para_los_demas(entrar, ana):
    respuesta = entrar(con_perfil(ana)).get(url(hacer_ficha(es_privada=True)))

    assert respuesta.status_code == 404
