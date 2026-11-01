import pytest
from django import forms
from django.core.exceptions import ValidationError

from apps.core.filtros import NoOfensivo, contiene_ofensivo


@pytest.mark.parametrize(
    "texto",
    [
        "puto",
        "Sos un PELOTUDO",
        "hijo de puta",
        "PÚTA",
        "Imbécil",
        "m13rd4",
        "puuuuto",
        "forrrro",
        "JuanPuto",
        "pelotudo_99",
        "hdp",
    ],
)
def test_detecta_texto_ofensivo(texto):
    assert contiene_ofensivo(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "Ana",
        "JuanPerez",
        "María José",
        "Compasivo",
        "Putumayo",
        "Concha",
        "Pitufo",
        "Foro",
        "Armando",
        "Escuela",
        "Computadora",
        "ana1980",
    ],
)
def test_no_marca_texto_normal(texto):
    assert not contiene_ofensivo(texto)


def test_texto_vacio_o_nulo_no_es_ofensivo():
    assert not contiene_ofensivo("")
    assert not contiene_ofensivo(None)


def test_el_validador_rechaza_con_el_mensaje_indicado():
    validador = NoOfensivo("Nombre ofensivo")
    with pytest.raises(ValidationError) as error:
        validador("Sos puto")
    assert error.value.messages == ["Nombre ofensivo"]
    validador("Ana")


def test_el_validador_funciona_dentro_de_un_formulario():
    class FormularioDePrueba(forms.Form):
        nombre = forms.CharField(validators=[NoOfensivo("Nombre ofensivo")])

    malo = FormularioDePrueba({"nombre": "pelotudo"})
    assert not malo.is_valid()
    assert malo.errors["nombre"] == ["Nombre ofensivo"]
    assert FormularioDePrueba({"nombre": "Ana"}).is_valid()


def test_dos_validadores_con_el_mismo_mensaje_son_iguales():
    assert NoOfensivo("x") == NoOfensivo("x")
    assert NoOfensivo("x") != NoOfensivo("y")
