import pytest
from django.utils import timezone

from apps.fichas import servicios
from apps.fichas.models import FichaAnimal

pytestmark = pytest.mark.django_db

DATOS = {"especie": "perro", "tamano": "mediano", "color": "marrón"}


def test_el_hallazgo_crea_una_ficha_sin_responsable_y_privada():
    ficha = servicios.crear_ficha_sin_responsable(DATOS)

    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE
    assert ficha.responsable is None
    assert ficha.es_privada is True
    assert ficha.especie == "perro"


def test_si_alguien_lo_tiene_consigo_queda_a_su_cargo_y_corre_el_plazo(ana):
    ficha = servicios.crear_ficha_sin_responsable(DATOS, cuidador=ana)

    assert ficha.cuidador == ana
    assert ficha.responsable is None
    assert ficha.sin_responsable_desde == timezone.localdate()


def test_si_nadie_lo_tiene_no_queda_a_cargo_de_nadie_ni_corre_el_plazo():
    ficha = servicios.crear_ficha_sin_responsable(DATOS)

    assert ficha.cuidador is None
    assert ficha.sin_responsable_desde is None


def test_ignora_los_campos_que_no_son_editables(ana):
    datos = {**DATOS, "estado": FichaAnimal.Estado.EN_ADOPCION, "responsable": ana}

    ficha = servicios.crear_ficha_sin_responsable(datos)

    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE
    assert ficha.responsable is None
