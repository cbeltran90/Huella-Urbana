import pytest

from apps.publicaciones.telefonos import enlace_whatsapp

WHATSAPP = "https://wa.me/5492901444444"


@pytest.mark.parametrize(
    "telefono",
    [
        "+54 9 2901 444444",
        "+54 2901 444444",
        "2901 444444",
        "02901 444444",
        "2901 15 444444",
        "(2901) 15-444444",
        "444444",
        "15 444444",
    ],
)
def test_las_formas_de_escribir_un_celular_de_ushuaia_llevan_al_mismo_whatsapp(telefono):
    assert enlace_whatsapp(telefono) == WHATSAPP


def test_un_celular_de_otra_ciudad_conserva_su_caracteristica():
    assert enlace_whatsapp("+54 9 11 2345 6789") == "https://wa.me/5491123456789"


def test_un_numero_local_que_empieza_con_54_no_se_confunde_con_el_codigo_de_pais():
    assert enlace_whatsapp("544444") == "https://wa.me/5492901544444"


@pytest.mark.parametrize("telefono", ["", "123", "2901 4444", "+1 555 123 4567 89"])
def test_si_no_se_puede_armar_el_numero_no_hay_enlace(telefono):
    assert enlace_whatsapp(telefono) == ""
