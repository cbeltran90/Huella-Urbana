import pytest

from apps.cuentas.models import Domicilio
from apps.transito import servicios


def vivienda(tipo, patio, **hogar):
    return Domicilio(tipo_vivienda=tipo, tiene_patio=patio, **hogar)


@pytest.mark.parametrize(
    ("tipo", "patio", "esperado"),
    [
        ("casa", True, 5),
        ("casa", False, 3),
        ("departamento", True, 3),
        ("departamento", False, 1),
        ("otra", True, 3),
        ("otra", False, 1),
    ],
)
def test_el_estimado_sale_del_tipo_de_vivienda_y_el_patio(tipo, patio, esperado):
    assert servicios.cupo_estimado(vivienda(tipo, patio)) == esperado


@pytest.mark.parametrize(
    "hogar",
    [
        {"convivientes": 0, "hay_ninos": False, "mascotas_propias": 0},
        {"convivientes": 20, "hay_ninos": True, "mascotas_propias": 30},
    ],
)
def test_convivientes_ninos_y_mascotas_no_cambian_el_estimado(hogar):
    assert servicios.cupo_estimado(vivienda("casa", True, **hogar)) == 5
    assert servicios.cupo_estimado(vivienda("departamento", False, **hogar)) == 1


def test_el_mayor_estimado_es_5_y_el_menor_1():
    estimados = [
        servicios.cupo_estimado(vivienda(tipo, patio))
        for tipo in ("casa", "departamento", "otra")
        for patio in (True, False)
    ]

    assert max(estimados) == servicios.MAX_CUPO_ESTIMADO == 5
    assert min(estimados) == 1


def test_sin_domicilio_no_hay_estimado():
    assert servicios.cupo_estimado(None) is None


@pytest.mark.parametrize(
    ("tipo", "patio"),
    [("", True), (None, True), ("casa", None), ("castillo", True)],
)
def test_con_datos_de_vivienda_faltantes_o_desconocidos_no_hay_estimado(tipo, patio):
    assert servicios.cupo_estimado(vivienda(tipo, patio)) is None
