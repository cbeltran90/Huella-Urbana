import pytest
from model_bakery import baker

from apps.cuentas.eliminacion import eliminar_cuenta, impedimentos_para_eliminar
from apps.cuentas.models import EstadoCuenta, Usuario
from apps.fichas.models import FichaAnimal
from apps.transito import servicios
from apps.transito.models import Postulacion

CLAVE = "clave-de-prueba-1"
Estado = Postulacion.Estado

pytestmark = pytest.mark.django_db


def crear_usuario(nombre):
    return Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


@pytest.fixture
def lucia():
    return crear_usuario("lucia")


@pytest.fixture
def martin():
    return crear_usuario("martin")


def ficha_en_adopcion(**campos):
    return baker.make(FichaAnimal, especie="perro", estado=FichaAnimal.Estado.EN_ADOPCION, **campos)


def postular(usuario, ficha, estado=Estado.PENDIENTE, tipo=Postulacion.Tipo.TRANSITO):
    return Postulacion.objects.create(
        usuario=usuario, ficha=ficha, tipo=tipo, contacto="2901-555555", estado=estado
    )


def test_sin_postulaciones_no_hay_eleccion_pendiente(lucia):
    assert servicios.tiene_eleccion_pendiente(lucia) is False


def test_una_postulacion_pendiente_no_cuenta(lucia):
    postular(lucia, ficha_en_adopcion())
    assert servicios.tiene_eleccion_pendiente(lucia) is False


def test_una_postulacion_descartada_no_cuenta(lucia):
    postular(lucia, ficha_en_adopcion(), estado=Estado.DESCARTADA)
    assert servicios.tiene_eleccion_pendiente(lucia) is False


def test_la_persona_elegida_tiene_una_eleccion_pendiente(lucia):
    postular(lucia, ficha_en_adopcion(), estado=Estado.ELEGIDA)
    assert servicios.tiene_eleccion_pendiente(lucia) is True


def test_quien_tiene_el_animal_a_cargo_tiene_una_eleccion_pendiente(lucia, martin):
    ficha = ficha_en_adopcion(cuidador=martin)
    postular(lucia, ficha, estado=Estado.ELEGIDA)
    assert servicios.tiene_eleccion_pendiente(martin) is True


def test_el_responsable_tiene_una_eleccion_pendiente_con_un_adoptante_elegido(lucia, martin):
    ficha = ficha_en_adopcion(responsable=martin)
    postular(lucia, ficha, estado=Estado.ELEGIDA, tipo=Postulacion.Tipo.ADOPCION)
    assert servicios.tiene_eleccion_pendiente(martin) is True


def test_una_eleccion_sobre_un_animal_ajeno_no_cuenta(lucia, martin):
    postular(lucia, ficha_en_adopcion(), estado=Estado.ELEGIDA)
    assert servicios.tiene_eleccion_pendiente(martin) is False


def test_una_eleccion_pendiente_impide_eliminar_la_cuenta(lucia):
    postular(lucia, ficha_en_adopcion(), estado=Estado.ELEGIDA)
    codigos = [impedimento.codigo for impedimento in impedimentos_para_eliminar(lucia)]
    assert "eleccion_pendiente" in codigos


def test_una_postulacion_pendiente_no_impide_eliminar_la_cuenta(lucia):
    postular(lucia, ficha_en_adopcion())
    assert impedimentos_para_eliminar(lucia) == []


def test_al_eliminar_la_cuenta_se_borran_sus_postulaciones(lucia, martin):
    postular(lucia, ficha_en_adopcion())
    postular(lucia, ficha_en_adopcion(), estado=Estado.DESCARTADA)
    ajena = postular(martin, ficha_en_adopcion())

    eliminar_cuenta(lucia)

    assert not Postulacion.objects.filter(usuario=lucia).exists()
    assert Postulacion.objects.filter(pk=ajena.pk).exists()
