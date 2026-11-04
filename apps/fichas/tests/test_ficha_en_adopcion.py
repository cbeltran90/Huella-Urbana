import pytest

from apps.fichas import servicios
from apps.fichas.models import FichaAnimal

pytestmark = pytest.mark.django_db

DATOS = {"especie": "perro", "tamano": "mediano", "color": "marrón"}


def test_el_alta_directa_crea_la_ficha_en_adopcion_a_cargo_de_quien_la_da(ana):
    ficha = servicios.crear_ficha_en_adopcion(DATOS, cuidador=ana)

    assert ficha.estado == FichaAnimal.Estado.EN_ADOPCION
    assert ficha.cuidador == ana
    assert ficha.responsable is None
    assert ficha.especie == "perro"


def test_la_ficha_en_adopcion_es_publica(ana):
    ficha = servicios.crear_ficha_en_adopcion(DATOS, cuidador=ana)

    assert ficha.es_privada is False


def test_ignora_los_campos_que_no_son_editables(ana, beto):
    ficha = servicios.crear_ficha_en_adopcion(
        {**DATOS, "estado": FichaAnimal.Estado.REGISTRADO, "responsable": beto}, cuidador=ana
    )

    assert ficha.estado == FichaAnimal.Estado.EN_ADOPCION
    assert ficha.responsable is None
