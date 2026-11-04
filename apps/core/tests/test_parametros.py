import pytest
from constance import settings as ajustes
from constance.forms import ConstanceForm
from constance.utils import get_values


def formulario(**cambios):
    """El formulario de parámetros del panel, con los valores actuales y los cambios pedidos."""
    actuales = get_values()
    datos = {nombre: actuales[nombre] for nombre in ajustes.CONFIG}
    datos.update(cambios)
    datos["version"] = ConstanceForm(initial=actuales).initial["version"]
    return ConstanceForm(initial=actuales, data=datos)


FUERA_DE_RANGO = [
    ("RADIO_DOMICILIO_METROS", 0),
    ("RADIO_DOMICILIO_METROS", 49),
    ("RADIO_DOMICILIO_METROS", 1001),
    ("DIAS_PRIMERA_SUSPENSION", 0),
    ("DIAS_PRIMERA_SUSPENSION", -1),
    ("DIAS_PRIMERA_SUSPENSION", 366),
    ("DIAS_AUSENCIA_RESPONSABLE", 0),
    ("DIAS_AVISO_VENCIMIENTO", 0),
    ("DIAS_PUBLICAR_VENCIMIENTO", 0),
    ("DURACION_MINIMA_TRANSITO_DIAS", 0),
    ("DIAS_RETENCION_NOTIFICACIONES", 0),
    ("MAX_PUBLICACIONES_HORA", 0),
    ("MAX_PUBLICACIONES_HORA", 101),
    ("UMBRAL_SIMILITUD", -0.1),
    ("UMBRAL_SIMILITUD", 1.5),
    ("UMBRAL_PHASH", -1),
    ("UMBRAL_PHASH", 65),
]


@pytest.mark.django_db
def test_los_valores_actuales_son_validos():
    assert formulario().is_valid()


@pytest.mark.django_db
@pytest.mark.parametrize(("nombre", "valor"), FUERA_DE_RANGO)
def test_un_valor_fuera_de_rango_se_rechaza(nombre, valor):
    form = formulario(**{nombre: valor})

    assert not form.is_valid()
    assert nombre in form.errors


@pytest.mark.django_db
def test_un_valor_que_no_es_un_numero_se_rechaza():
    form = formulario(RADIO_DOMICILIO_METROS="muchos")

    assert not form.is_valid()
    assert "RADIO_DOMICILIO_METROS" in form.errors


@pytest.mark.django_db
def test_un_valor_dentro_del_rango_se_acepta():
    form = formulario(RADIO_DOMICILIO_METROS=200, UMBRAL_SIMILITUD=0.9, UMBRAL_PHASH=0)

    assert form.is_valid()


def test_todo_parametro_declara_su_rango():
    sin_rango = [
        nombre
        for nombre, opciones in ajustes.CONFIG.items()
        if len(opciones) != 3 or opciones[2] not in ajustes.ADDITIONAL_FIELDS
    ]
    assert sin_rango == []
