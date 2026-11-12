import pytest
from django.urls import reverse

from apps.fichas.models import FichaAnimal
from apps.transito.models import Postulacion

from .conftest import BACKEND_MODELO, hacer_ficha

pytestmark = pytest.mark.django_db


def concretar(ficha):
    return reverse("adopcion:concretar", args=[ficha.pk])


def cancelar(ficha):
    return reverse("adopcion:cancelar", args=[ficha.pk])


def elegir(ficha, usuario):
    return Postulacion.objects.create(
        ficha=ficha,
        usuario=usuario,
        tipo=Postulacion.Tipo.ADOPCION,
        estado=Postulacion.Estado.ELEGIDA,
        contacto="2901 444444",
    )


@pytest.fixture
def entrar(client):
    def _entrar(usuario):
        client.force_login(usuario, backend=BACKEND_MODELO)
        return client

    return _entrar


def test_pide_confirmar_la_entrega(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto, nombre="Firulais")
    elegir(ficha, ana)

    html = entrar(beto).get(concretar(ficha)).content.decode()

    assert "¿Firulais ya está con Ana?" in html
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.EN_ADOPCION


def test_al_confirmar_vuelve_a_la_ficha_adoptada(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    elegir(ficha, ana)

    respuesta = entrar(beto).post(concretar(ficha))

    assert respuesta.url == f"{reverse('fichas:detalle', args=[ficha.pk])}?adoptada=1"
    ficha.refresh_from_db()
    assert ficha.responsable == ana


def test_si_ya_no_puede_ver_la_ficha_va_a_los_disponibles(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto, es_privada=True)
    elegir(ficha, ana)

    respuesta = entrar(beto).post(concretar(ficha))

    assert respuesta.url == reverse("publicaciones:disponibles")


def test_otra_persona_no_puede_concretar_ni_cancelar(entrar, ana, beto, carla):
    ficha = hacer_ficha(cuidador=beto)
    elegir(ficha, ana)
    cliente = entrar(carla)

    assert cliente.get(concretar(ficha)).status_code == 403
    assert cliente.get(cancelar(ficha)).status_code == 403


def test_sin_adoptante_elegido_lo_dice(entrar, beto):
    html = entrar(beto).get(concretar(hacer_ficha(cuidador=beto))).content.decode()

    assert "Todavía no se eligió quién la adopta." in html
    assert "Sí, ya está con" not in html


def test_al_cancelar_vuelve_a_los_postulantes(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    elegida = elegir(ficha, ana)

    respuesta = entrar(beto).post(cancelar(ficha))

    assert respuesta.url == reverse("adopcion:postulantes", args=[ficha.pk])
    elegida.refresh_from_db()
    assert elegida.estado == Postulacion.Estado.DESCARTADA


def test_la_pantalla_de_postulantes_ofrece_concretar_o_cancelar(entrar, ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    elegir(ficha, ana)

    html = entrar(beto).get(reverse("adopcion:postulantes", args=[ficha.pk])).content.decode()

    assert concretar(ficha) in html
    assert cancelar(ficha) in html
