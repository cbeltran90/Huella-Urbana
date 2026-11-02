import pytest

from apps.fichas.forms import MENSAJE_EDAD, MENSAJE_TEXTO_OFENSIVO, FichaForm

pytestmark = pytest.mark.django_db


def datos(**cambios):
    base = {
        "especie": "perro",
        "nombre": "Firulais",
        "tamano": "mediano",
        "edad_estimada": "3",
        "color": "marrón",
        "raza": "mestizo",
    }
    return {**base, **cambios}


def test_datos_validos():
    form = FichaForm(datos())

    assert form.is_valid(), form.errors
    assert form.cleaned_data["edad_estimada"] == "3"


def test_solo_la_especie_es_obligatoria():
    form = FichaForm({"especie": "gato"})

    assert form.is_valid(), form.errors
    assert form.cleaned_data["edad_estimada"] == ""


@pytest.mark.parametrize("especie", ["", "pez"])
def test_la_especie_es_obligatoria_y_del_catalogo(especie):
    form = FichaForm(datos(especie=especie))

    assert not form.is_valid()
    assert "especie" in form.errors


def test_el_tamano_tiene_que_ser_del_catalogo():
    form = FichaForm(datos(tamano="gigante"))

    assert not form.is_valid()
    assert "tamano" in form.errors


@pytest.mark.parametrize("campo", ["nombre", "color", "raza", "temperamento"])
def test_texto_ofensivo_se_rechaza(campo):
    form = FichaForm(datos(**{campo: "mierda"}))

    assert not form.is_valid()
    assert form.errors[campo] == [MENSAJE_TEXTO_OFENSIVO]


@pytest.mark.parametrize("edad", ["abc", "-1", "31", "2.5"])
def test_la_edad_tiene_que_ser_un_numero_de_anios_razonable(edad):
    form = FichaForm(datos(edad_estimada=edad))

    assert not form.is_valid()
    assert form.errors["edad_estimada"] == [MENSAJE_EDAD]
