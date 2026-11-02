import pytest
from django.contrib.auth.models import AnonymousUser
from model_bakery import baker

from apps.fichas import permisos
from apps.fichas.models import FichaAnimal

Estado = FichaAnimal.Estado

pytestmark = pytest.mark.django_db


def test_una_ficha_privada_la_ven_responsable_cuidador_y_moderador(ana, beto, carla, moderador):
    ficha = baker.make(FichaAnimal, responsable=ana, cuidador=beto, es_privada=True)

    assert permisos.puede_ver(ana, ficha)
    assert permisos.puede_ver(beto, ficha)
    assert permisos.puede_ver(moderador, ficha)
    assert not permisos.puede_ver(carla, ficha)
    assert not permisos.puede_ver(AnonymousUser(), ficha)


def test_una_ficha_que_no_es_privada_la_ve_cualquier_usuario(ana, carla):
    ficha = baker.make(FichaAnimal, responsable=ana, es_privada=False)

    assert permisos.puede_ver(carla, ficha)


def test_editan_responsable_cuidador_y_moderador(ana, beto, carla, moderador):
    ficha = baker.make(FichaAnimal, responsable=ana, cuidador=beto)

    assert permisos.puede_editar(ana, ficha)
    assert permisos.puede_editar(beto, ficha)
    assert permisos.puede_editar(moderador, ficha)
    assert not permisos.puede_editar(carla, ficha)
    assert not permisos.puede_editar(AnonymousUser(), ficha)


def test_solo_el_responsable_da_de_baja_una_ficha_registrada(ana, beto, moderador):
    ficha = baker.make(FichaAnimal, responsable=ana, cuidador=beto, estado=Estado.REGISTRADO)

    assert permisos.puede_dar_de_baja(ana, ficha)
    assert not permisos.puede_dar_de_baja(beto, ficha)
    assert not permisos.puede_dar_de_baja(moderador, ficha)


@pytest.mark.parametrize("estado", [Estado.SIN_RESPONSABLE, Estado.EN_ADOPCION, Estado.EN_TRANSITO])
def test_no_hay_baja_en_los_demas_estados(ana, estado):
    ficha = baker.make(FichaAnimal, responsable=ana, estado=estado)

    assert not permisos.puede_dar_de_baja(ana, ficha)


def test_sin_adopcion_registrada_la_ficha_no_figura_como_adoptada(ana):
    ficha = baker.make(FichaAnimal, responsable=ana)

    assert permisos.tiene_adopcion_registrada(ficha) is False
