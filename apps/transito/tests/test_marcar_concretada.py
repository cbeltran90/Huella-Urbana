import pytest
from model_bakery import baker

from apps.cuentas.eliminacion import impedimentos_para_eliminar
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


def ficha_en_adopcion(**campos):
    return baker.make(FichaAnimal, especie="perro", estado=FichaAnimal.Estado.EN_ADOPCION, **campos)


def postular(usuario, ficha, estado):
    return Postulacion.objects.create(
        usuario=usuario,
        ficha=ficha,
        tipo=Postulacion.Tipo.TRANSITO,
        contacto="2901-555555",
        estado=estado,
    )


def test_una_postulacion_elegida_pasa_a_concretada():
    postulacion = postular(crear_usuario("lucia"), ficha_en_adopcion(), Estado.ELEGIDA)

    resultado = servicios.marcar_concretada(postulacion)

    postulacion.refresh_from_db()
    assert postulacion.estado == Estado.CONCRETADA
    assert resultado.estado == Estado.CONCRETADA


def test_la_instancia_recibida_tambien_queda_concretada():
    postulacion = postular(crear_usuario("lucia"), ficha_en_adopcion(), Estado.ELEGIDA)
    servicios.marcar_concretada(postulacion)
    assert postulacion.estado == Estado.CONCRETADA


@pytest.mark.parametrize("estado", [Estado.PENDIENTE, Estado.DESCARTADA, Estado.CONCRETADA])
def test_solo_se_concreta_una_postulacion_elegida(estado):
    postulacion = postular(crear_usuario("lucia"), ficha_en_adopcion(), estado)

    with pytest.raises(servicios.PostulacionNoElegida):
        servicios.marcar_concretada(postulacion)

    postulacion.refresh_from_db()
    assert postulacion.estado == estado


def test_no_se_concreta_dos_veces():
    postulacion = postular(crear_usuario("lucia"), ficha_en_adopcion(), Estado.ELEGIDA)
    servicios.marcar_concretada(postulacion)
    with pytest.raises(servicios.PostulacionNoElegida):
        servicios.marcar_concretada(postulacion)


def test_concretada_deja_de_ser_una_eleccion_pendiente_para_los_dos():
    lucia = crear_usuario("lucia")
    martin = crear_usuario("martin")
    postulacion = postular(lucia, ficha_en_adopcion(cuidador=martin), Estado.ELEGIDA)
    assert servicios.tiene_eleccion_pendiente(lucia) is True
    assert servicios.tiene_eleccion_pendiente(martin) is True

    servicios.marcar_concretada(postulacion)

    assert servicios.tiene_eleccion_pendiente(lucia) is False
    assert servicios.tiene_eleccion_pendiente(martin) is False


def test_concretada_ya_no_impide_eliminar_la_cuenta():
    lucia = crear_usuario("lucia")
    postulacion = postular(lucia, ficha_en_adopcion(), Estado.ELEGIDA)
    assert impedimentos_para_eliminar(lucia) != []

    servicios.marcar_concretada(postulacion)

    assert impedimentos_para_eliminar(lucia) == []
