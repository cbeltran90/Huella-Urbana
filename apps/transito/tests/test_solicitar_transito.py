import pytest
from django.contrib.auth.models import AnonymousUser

from apps.cuentas.models import EstadoCuenta, Rol, Usuario
from apps.fichas.models import FichaAnimal
from apps.transito import solicitud
from apps.transito.solicitud import ContactoInvalido, SolicitudNoPermitida

CLAVE = "clave-de-prueba-1"

pytestmark = pytest.mark.django_db


def crear_usuario(nombre, **campos):
    return Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, **campos
    )


def crear_ficha(**campos):
    datos = {
        "nombre": "Bruno",
        "especie": "perro",
        "tamano": "mediano",
        "estado": FichaAnimal.Estado.SIN_RESPONSABLE,
        "es_privada": True,
        **campos,
    }
    return FichaAnimal.objects.create(**datos)


@pytest.fixture
def cuidador():
    return crear_usuario("carla")


@pytest.fixture
def moderador():
    return crear_usuario("mora", rol=Rol.MODERADOR)


def test_el_cuidador_puede_solicitar(cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    assert solicitud.puede_solicitar(cuidador, ficha) is True


def test_un_moderador_puede_solicitar(moderador, cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    assert solicitud.puede_solicitar(moderador, ficha) is True


def test_otro_usuario_no_puede_solicitar(cuidador):
    otra = crear_usuario("otra")
    ficha = crear_ficha(cuidador=cuidador)
    assert solicitud.puede_solicitar(otra, ficha) is False


def test_un_visitante_no_puede_solicitar(cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    assert solicitud.puede_solicitar(AnonymousUser(), ficha) is False


def test_sin_cuidador_solo_puede_un_moderador(moderador):
    otra = crear_usuario("otra")
    ficha = crear_ficha(cuidador=None)
    assert solicitud.puede_solicitar(otra, ficha) is False
    assert solicitud.puede_solicitar(moderador, ficha) is True


@pytest.mark.parametrize(
    "estado",
    [
        FichaAnimal.Estado.REGISTRADO,
        FichaAnimal.Estado.EN_ADOPCION,
        FichaAnimal.Estado.EN_TRANSITO,
    ],
)
def test_solo_se_solicita_con_la_ficha_sin_responsable(cuidador, estado):
    ficha = crear_ficha(estado=estado, cuidador=cuidador)
    assert solicitud.puede_solicitar(cuidador, ficha) is False


def test_la_ficha_pasa_a_en_adopcion_y_queda_publica(cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    solicitud.solicitar_transito(ficha, cuidador)
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.EN_ADOPCION
    assert ficha.es_privada is False
    assert ficha.cuidador == cuidador


def test_quien_no_puede_no_cambia_la_ficha(cuidador):
    otra = crear_usuario("otra")
    ficha = crear_ficha(cuidador=cuidador)
    with pytest.raises(SolicitudNoPermitida):
        solicitud.solicitar_transito(ficha, otra)
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE
    assert ficha.es_privada is True


def test_si_otro_cambio_el_estado_no_se_pisa(cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    FichaAnimal.objects.filter(pk=ficha.pk).update(estado=FichaAnimal.Estado.REGISTRADO)
    with pytest.raises(SolicitudNoPermitida):
        solicitud.solicitar_transito(ficha, cuidador)
    assert FichaAnimal.objects.get(pk=ficha.pk).estado == FichaAnimal.Estado.REGISTRADO


def test_el_moderador_carga_el_contacto_si_no_hay_cuidador(moderador):
    ficha = crear_ficha(cuidador=None)
    solicitud.solicitar_transito(ficha, moderador, contacto="  Vecina, 2901 555-0101 ")
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.EN_ADOPCION
    assert ficha.cuidador_contacto == "Vecina, 2901 555-0101"


def test_el_contacto_se_ignora_si_hay_cuidador(moderador, cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    solicitud.solicitar_transito(ficha, moderador, contacto="Otra persona")
    ficha.refresh_from_db()
    assert ficha.cuidador_contacto == ""


def test_el_contacto_se_ignora_si_no_es_moderador(cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    solicitud.solicitar_transito(ficha, cuidador, contacto="Otra persona")
    ficha.refresh_from_db()
    assert ficha.cuidador_contacto == ""


def test_un_contacto_demasiado_largo_se_rechaza(moderador):
    ficha = crear_ficha(cuidador=None)
    with pytest.raises(ContactoInvalido):
        solicitud.solicitar_transito(ficha, moderador, contacto="x" * 101)
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE
