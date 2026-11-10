import pytest
from model_bakery import baker

from apps.cuentas.models import EstadoCuenta, Usuario
from apps.fichas.models import FichaAnimal
from apps.transito import postulaciones
from apps.transito.models import PerfilTransito, Postulacion
from apps.transito.postulaciones import RetiroPostulacionNoPermitido

CLAVE = "clave-de-prueba-1"
Estado = Postulacion.Estado

pytestmark = pytest.mark.django_db


def crear_hogar(nombre):
    usuario = Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    PerfilTransito.objects.create(
        usuario=usuario,
        especies_aceptadas="perro",
        tamano_maximo="mediano",
        duracion_maxima_dias=30,
        cupo_declarado=2,
    )
    return usuario


def ficha_en_adopcion():
    return baker.make(FichaAnimal, especie="perro", estado=FichaAnimal.Estado.EN_ADOPCION)


def postular(usuario, ficha, estado=Estado.PENDIENTE):
    return Postulacion.objects.create(
        usuario=usuario,
        ficha=ficha,
        tipo=Postulacion.Tipo.TRANSITO,
        contacto="2901-555555",
        estado=estado,
    )


def test_el_hogar_retira_su_postulacion_pendiente_y_queda_descartada():
    lucia = crear_hogar("lucia")
    postulacion = postular(lucia, ficha_en_adopcion())

    resultado = postulaciones.retirar_postulacion(postulacion, lucia)

    postulacion.refresh_from_db()
    assert postulacion.estado == Estado.DESCARTADA
    assert resultado.estado == Estado.DESCARTADA
    assert postulacion.activa is False


def test_la_instancia_recibida_tambien_queda_descartada():
    lucia = crear_hogar("lucia")
    postulacion = postular(lucia, ficha_en_adopcion())
    postulaciones.retirar_postulacion(postulacion, lucia)
    assert postulacion.estado == Estado.DESCARTADA


def test_no_se_puede_retirar_la_postulacion_de_otra_persona():
    lucia = crear_hogar("lucia")
    martin = crear_hogar("martin")
    postulacion = postular(lucia, ficha_en_adopcion())

    with pytest.raises(RetiroPostulacionNoPermitido) as error:
        postulaciones.retirar_postulacion(postulacion, martin)

    assert str(error.value) == postulaciones.MENSAJE_NO_ES_SUYA
    postulacion.refresh_from_db()
    assert postulacion.estado == Estado.PENDIENTE


@pytest.mark.parametrize("estado", [Estado.ELEGIDA, Estado.DESCARTADA, Estado.CONCRETADA])
def test_solo_se_retira_una_postulacion_pendiente(estado):
    lucia = crear_hogar("lucia")
    postulacion = postular(lucia, ficha_en_adopcion(), estado)

    with pytest.raises(RetiroPostulacionNoPermitido) as error:
        postulaciones.retirar_postulacion(postulacion, lucia)

    assert str(error.value) == postulaciones.MENSAJE_NO_PENDIENTE
    postulacion.refresh_from_db()
    assert postulacion.estado == estado


def test_despues_de_retirarla_puede_volver_a_postularse():
    lucia = crear_hogar("lucia")
    ficha = ficha_en_adopcion()
    postulaciones.retirar_postulacion(postular(lucia, ficha), lucia)

    nueva = postulaciones.postular_transito(lucia, ficha, "2901-555555")

    assert nueva.estado == Estado.PENDIENTE
    assert ficha.postulaciones.count() == 2


def test_retirar_una_no_toca_las_postulaciones_de_otros_hogares():
    lucia = crear_hogar("lucia")
    martin = crear_hogar("martin")
    ficha = ficha_en_adopcion()
    de_lucia = postular(lucia, ficha)
    de_martin = postular(martin, ficha)

    postulaciones.retirar_postulacion(de_lucia, lucia)

    de_martin.refresh_from_db()
    assert de_martin.estado == Estado.PENDIENTE
