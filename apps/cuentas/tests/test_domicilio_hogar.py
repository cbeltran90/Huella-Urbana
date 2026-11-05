import pytest
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError

from apps.cuentas.models import CAMPOS_HOGAR, Domicilio, EstadoCuenta, Usuario

CLAVE = "clave-de-prueba-1"
EXACTO = Point(-68.3030, -54.8019, srid=4326)
DESPLAZADO = Point(-68.3040, -54.8025, srid=4326)


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def hogar(**cambios):
    datos = {
        "tipo_vivienda": "casa",
        "tiene_patio": True,
        "convivientes": 2,
        "hay_ninos": False,
        "mascotas_propias": 1,
    }
    return {**datos, **cambios}


def crear(usuario, **campos):
    return Domicilio.objects.create(
        usuario=usuario, ubicacion=EXACTO, ubicacion_desplazada=DESPLAZADO, **campos
    )


@pytest.mark.django_db
def test_se_puede_guardar_el_domicilio_sin_datos_del_hogar(ana):
    domicilio = crear(ana)

    domicilio.full_clean()
    assert domicilio.hogar_faltante() == list(CAMPOS_HOGAR)
    assert not domicilio.hogar_completo


@pytest.mark.django_db
def test_con_todos_los_datos_el_hogar_esta_completo(ana):
    domicilio = crear(ana, **hogar())

    domicilio.full_clean()
    assert domicilio.hogar_faltante() == []
    assert domicilio.hogar_completo


@pytest.mark.django_db
def test_un_cero_y_un_no_cuentan_como_respuesta(ana):
    domicilio = crear(
        ana, **hogar(tiene_patio=False, convivientes=0, hay_ninos=False, mascotas_propias=0)
    )

    assert domicilio.hogar_completo


@pytest.mark.django_db
def test_se_indica_que_dato_falta(ana):
    domicilio = crear(ana, **hogar(hay_ninos=None, tipo_vivienda=""))

    assert domicilio.hogar_faltante() == ["tipo_vivienda", "hay_ninos"]
    assert not domicilio.hogar_completo


@pytest.mark.django_db
def test_los_datos_se_guardan_y_se_leen(ana):
    crear(ana, **hogar(tipo_vivienda="departamento", tiene_patio=False))

    guardado = Domicilio.objects.get(usuario=ana)
    assert guardado.tipo_vivienda == "departamento"
    assert guardado.tiene_patio is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalido",
    [
        {"tipo_vivienda": "castillo"},
        {"convivientes": -1},
        {"convivientes": 21},
        {"mascotas_propias": -1},
        {"mascotas_propias": 31},
    ],
)
def test_un_valor_fuera_de_rango_no_es_valido(ana, invalido):
    domicilio = crear(ana, **hogar())
    for campo, valor in invalido.items():
        setattr(domicilio, campo, valor)

    with pytest.raises(ValidationError) as error:
        domicilio.full_clean()

    assert set(error.value.message_dict) == set(invalido)
