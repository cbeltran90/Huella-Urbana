import pytest
from django.db import IntegrityError, transaction
from model_bakery import baker

from apps.cuentas.models import EstadoCuenta, Usuario
from apps.fichas.models import FichaAnimal
from apps.transito.models import Postulacion

CLAVE = "clave-de-prueba-1"

pytestmark = pytest.mark.django_db


def crear_usuario(nombre):
    return Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


@pytest.fixture
def ficha():
    return baker.make(FichaAnimal, especie="perro", estado=FichaAnimal.Estado.EN_ADOPCION)


def postular(usuario, ficha, **campos):
    datos = {"tipo": Postulacion.Tipo.TRANSITO, "contacto": "2901-555555", **campos}
    return Postulacion.objects.create(usuario=usuario, ficha=ficha, **datos)


def test_una_postulacion_nueva_queda_pendiente_y_activa(ficha):
    postulacion = postular(crear_usuario("lucia"), ficha)
    assert postulacion.estado == Postulacion.Estado.PENDIENTE
    assert postulacion.activa is True
    assert postulacion.fecha is not None


@pytest.mark.parametrize(
    ("estado", "activa"),
    [
        (Postulacion.Estado.PENDIENTE, True),
        (Postulacion.Estado.ELEGIDA, True),
        (Postulacion.Estado.DESCARTADA, False),
        (Postulacion.Estado.CONCRETADA, False),
    ],
)
def test_solo_pendiente_y_elegida_estan_activas(ficha, estado, activa):
    assert postular(crear_usuario("lucia"), ficha, estado=estado).activa is activa


def test_no_puede_haber_dos_postulaciones_activas_de_la_misma_persona_para_una_ficha(ficha):
    lucia = crear_usuario("lucia")
    postular(lucia, ficha)
    with pytest.raises(IntegrityError), transaction.atomic():
        postular(lucia, ficha, tipo=Postulacion.Tipo.ADOPCION)


def test_una_elegida_tambien_cuenta_como_activa(ficha):
    lucia = crear_usuario("lucia")
    postular(lucia, ficha, estado=Postulacion.Estado.ELEGIDA)
    with pytest.raises(IntegrityError), transaction.atomic():
        postular(lucia, ficha)


def test_puede_volver_a_postularse_si_la_anterior_fue_descartada(ficha):
    lucia = crear_usuario("lucia")
    postular(lucia, ficha, estado=Postulacion.Estado.DESCARTADA)
    nueva = postular(lucia, ficha)
    assert nueva.activa is True


def test_puede_volver_a_postularse_si_la_anterior_fue_concretada(ficha):
    lucia = crear_usuario("lucia")
    postular(lucia, ficha, estado=Postulacion.Estado.CONCRETADA)
    nueva = postular(lucia, ficha)
    assert nueva.activa is True


def test_varias_personas_pueden_postularse_a_la_misma_ficha(ficha):
    postular(crear_usuario("lucia"), ficha)
    postular(crear_usuario("martin"), ficha)
    assert ficha.postulaciones.count() == 2


def test_la_misma_persona_puede_postularse_a_fichas_distintas(ficha):
    lucia = crear_usuario("lucia")
    otra = baker.make(FichaAnimal, especie="gato", estado=FichaAnimal.Estado.EN_ADOPCION)
    postular(lucia, ficha)
    postular(lucia, otra)
    assert lucia.postulaciones.count() == 2


def test_se_muestra_con_la_persona_la_ficha_y_el_estado(ficha):
    texto = str(postular(crear_usuario("lucia"), ficha))
    assert "Lucia" in texto
    assert "Pendiente" in texto
