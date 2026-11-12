import pytest
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.fichas.servicios import cambiar_estado
from apps.fichas.transiciones import (
    TRANSICIONES,
    TransicionInvalida,
    estado_inicial_permitido,
)

Estado = FichaAnimal.Estado

VALIDAS = sorted(TRANSICIONES)
INVALIDAS = [(o, d) for o in Estado for d in Estado if (o, d) not in TRANSICIONES]


@pytest.mark.django_db
@pytest.mark.parametrize(("origen", "destino"), VALIDAS)
def test_transicion_valida_cambia_el_estado(origen, destino):
    ficha = baker.make(FichaAnimal, estado=origen)

    cambiar_estado(ficha, destino, actor=None)

    ficha.refresh_from_db()
    assert ficha.estado == destino


@pytest.mark.django_db
@pytest.mark.parametrize(("origen", "destino"), INVALIDAS)
def test_transicion_invalida_se_rechaza_y_no_cambia_nada(origen, destino):
    ficha = baker.make(FichaAnimal, estado=origen)

    with pytest.raises(TransicionInvalida):
        cambiar_estado(ficha, destino, actor=None)

    ficha.refresh_from_db()
    assert ficha.estado == origen


@pytest.mark.parametrize(
    ("estado", "esperado"),
    [
        (Estado.REGISTRADO, True),
        (Estado.SIN_RESPONSABLE, True),
        (Estado.EN_ADOPCION, True),
        (Estado.EN_TRANSITO, False),  # no se puede nacer ya en un hogar
    ],
)
def test_estados_con_los_que_puede_nacer_una_ficha(estado, esperado):
    assert estado_inicial_permitido(estado) is esperado


@pytest.mark.django_db
def test_cambios_se_guardan_junto_con_el_estado(django_user_model):
    adoptante = django_user_model.objects.create_user(
        "ana", "ana@ejemplo.com", password="clave-de-prueba"
    )
    ficha = baker.make(FichaAnimal, estado=Estado.EN_ADOPCION, responsable=None)

    cambiar_estado(ficha, Estado.REGISTRADO, actor=adoptante, cambios={"responsable": adoptante})

    ficha.refresh_from_db()
    assert ficha.estado == Estado.REGISTRADO
    assert ficha.responsable == adoptante


@pytest.mark.django_db
def test_campo_no_modificable_se_rechaza_sin_cambiar_el_estado():
    ficha = baker.make(FichaAnimal, estado=Estado.EN_ADOPCION)

    with pytest.raises(ValueError, match="especie"):
        cambiar_estado(ficha, Estado.REGISTRADO, actor=None, cambios={"especie": "perro"})

    ficha.refresh_from_db()
    assert ficha.estado == Estado.EN_ADOPCION


@pytest.mark.django_db
@pytest.mark.parametrize("origen", [Estado.SIN_RESPONSABLE, Estado.EN_ADOPCION, Estado.EN_TRANSITO])
def test_al_volver_a_registrado_se_limpia_quien_la_tenia_a_cargo(origen, django_user_model):
    cuidador = django_user_model.objects.create_user(
        "cuidador@ejemplo.com", "Cuidador", "clave-de-prueba-1"
    )
    ficha = baker.make(
        FichaAnimal,
        estado=origen,
        cuidador=cuidador,
        cuidador_contacto="2901-555555",
        sin_responsable_desde="2026-11-01",
        es_privada=True,
    )

    cambiar_estado(ficha, Estado.REGISTRADO, actor=None)

    ficha.refresh_from_db()
    assert ficha.cuidador is None and ficha.cuidador_contacto == ""
    assert ficha.sin_responsable_desde is None
    assert ficha.es_privada is True  # no se toca
