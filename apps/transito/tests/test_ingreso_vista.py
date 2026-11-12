import pytest
from django.urls import reverse

from apps.fichas.models import FichaAnimal
from apps.transito.models import Alojamiento, Postulacion

from .test_ingreso import crear_hogar, crear_usuario, elegir_hogar, suspender

BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"

pytestmark = pytest.mark.django_db


def url_ingreso(ficha):
    return reverse("transito:registrar_ingreso", args=[ficha.pk])


def url_cancelar(ficha):
    return reverse("transito:cancelar_entrega", args=[ficha.pk])


@pytest.fixture
def beto():
    return crear_usuario("beto")


@pytest.fixture
def hogar():
    return crear_hogar("hogar")


@pytest.fixture
def ficha(beto, hogar):
    ficha = FichaAnimal.objects.create(
        nombre="Firulais",
        especie="perro",
        tamano="mediano",
        estado=FichaAnimal.Estado.EN_ADOPCION,
        es_privada=False,
        cuidador=beto,
        vacunado=True,
    )
    elegir_hogar(ficha, hogar)
    return ficha


@pytest.fixture
def entrar(client):
    def _entrar(usuario):
        client.force_login(usuario, backend=BACKEND_MODELO)
        return client

    return _entrar


def test_pide_confirmar_con_la_sanidad_de_la_ficha(entrar, ficha, beto):
    html = entrar(beto).get(url_ingreso(ficha)).content.decode()

    assert "¿Firulais ya está en el hogar de Hogar?" in html
    assert 'name="vacunado" checked' in html
    assert 'name="castrado" checked' not in html
    assert not Alojamiento.objects.exists()


def test_al_confirmar_registra_el_ingreso_y_vuelve_a_la_ficha(entrar, ficha, beto):
    respuesta = entrar(beto).post(url_ingreso(ficha), {"vacunado": "on", "castrado": "on"})

    assert respuesta.url == reverse("fichas:detalle", args=[ficha.pk])
    alojamiento = Alojamiento.objects.get()
    assert alojamiento.vacunado_al_ingreso and alojamiento.castrado_al_ingreso
    assert not alojamiento.desparasitado_al_ingreso


def test_si_ya_no_puede_ver_la_ficha_va_a_los_disponibles(entrar, beto, hogar):
    privada = FichaAnimal.objects.create(
        especie="perro", estado=FichaAnimal.Estado.EN_ADOPCION, es_privada=True, cuidador=beto
    )
    elegir_hogar(privada, hogar)

    respuesta = entrar(beto).post(url_ingreso(privada))

    assert respuesta.url == reverse("publicaciones:disponibles")


def test_si_el_hogar_esta_suspendido_lo_dice(entrar, ficha, beto, hogar):
    suspender(hogar)

    html = entrar(beto).post(url_ingreso(ficha)).content.decode()

    assert "Ese hogar ya no está disponible." in html
    assert url_cancelar(ficha) in html
    assert not Alojamiento.objects.exists()


def test_otra_persona_no_puede(entrar, ficha):
    cliente = entrar(crear_usuario("dario"))

    assert cliente.get(url_ingreso(ficha)).status_code == 403
    assert cliente.get(url_cancelar(ficha)).status_code == 403


def test_al_cancelar_vuelve_a_la_ficha(entrar, ficha, beto):
    respuesta = entrar(beto).post(url_cancelar(ficha))

    assert respuesta.url == reverse("fichas:detalle", args=[ficha.pk])
    assert Postulacion.objects.get().estado == Postulacion.Estado.DESCARTADA


def test_quien_entrega_ve_los_botones_en_la_ficha(entrar, ficha, beto):
    html = entrar(beto).get(reverse("fichas:detalle", args=[ficha.pk])).content.decode()

    assert url_ingreso(ficha) in html
    assert url_cancelar(ficha) in html


def test_el_hogar_elegido_ve_los_botones_en_la_ficha(entrar, ficha, hogar):
    html = entrar(hogar).get(reverse("fichas:detalle", args=[ficha.pk])).content.decode()

    assert url_ingreso(ficha) in html
    assert url_cancelar(ficha) in html
